"""
Migrado database client

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

import subprocess

from arango import ArangoClient
from arango.exceptions import TransactionExecuteError
from arango.http import DefaultHTTPClient
from arango.response import Response


class HTTPClient(DefaultHTTPClient):
    def __init__(self, timeout):
        self.timeout = timeout

    def send_request(self, session, method, url, params=None, data=None, headers=None, auth=None):
        response = session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            auth=auth,
            timeout=self.timeout
        )
        return Response(
            method=response.request.method,
            url=response.url,
            headers=response.headers,
            status_code=response.status_code,
            status_text=response.reason,
            raw_body=response.text,
        )

class MigrationClient:
    """Client for reading and writing state, running migrations against ArangoDB"""

    def __init__(self, tls, host, port, username, password, db, coll, timeout=1200):
        self.protocol = 'https' if tls else 'http'
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db
        self.coll_name = coll
        self.timeout = timeout

        http_client = HTTPClient(timeout=timeout)
        self.db_client = ArangoClient(f'{self.protocol}://{host}:{port}', http_client=http_client)

    @property
    def db(self):
        """Get database"""
        return self.db_client.db(self.db_name, self.username, self.password)

    @property
    def state_coll(self):
        """Get or create state collection"""
        if not self.db.has_collection(self.coll_name):
            return self.db.create_collection(self.coll_name)
        else:
            return self.db.collection(self.coll_name)

    def read_state(self):
        """Read state from state collection, or return default initial state"""
        if self.db.has_collection(self.coll_name) and self.state_coll.has('state'):
            state = self.state_coll.get('state')
        else:
            state = {'migration_id': '0000'}

        return state.get('migration_id')

    def read_schema(self):
        """Read schema from state collection"""
        if self.db.has_collection(self.coll_name) and self.state_coll.has('schema'):
            state = self.state_coll.get('schema')
        else:
            state = {'schema': {}}

        return state.get('schema')

    def write_state(self, migration_id):
        """Write given state to state collection"""
        state = {
            '_key': 'state',
            'migration_id': migration_id,
        }
        return self.state_coll.insert(state, overwrite=True, silent=True)

    def write_schema(self, schema):
        """Write given schema to state collection"""
        state = {
            '_key': 'schema',
            'schema': schema,
        }
        return self.state_coll.insert(state, overwrite=True, silent=True)

    def infer_schema(self, validation):
        """Infer schema from current database structure"""
        schema = {
            'collections': {},
            'edge_collections': {},
        }

        collections = self.db.collections()
        db_collections = [
            collection['name'] for collection in collections
            if (collection['type'] == 'document'
                and not collection['system']
                and not collection['name'] == self.coll_name)
        ]
        db_edge_collections = [
            collection['name'] for collection in collections
            if (collection['type'] == 'edge'
                and not collection['system'])
        ]

        for collection in db_collections:
            schema['collections'][collection] = None
            if validation:
                props = self.db.collection(collection).properties()
                collection_schema = props.get('schema')
                if collection_schema:
                    schema['collections'][collection] = {}
                    schema['collections'][collection]['schema'] = collection_schema

        for collection in db_edge_collections:
            schema['edge_collections'][collection] = None
            if validation:
                props = self.db.collection(collection).properties()
                collection_schema = props.get('schema')
                if collection_schema:
                    schema['edge_collections'][collection] = {}
                    schema['edge_collections'][collection]['schema'] = collection_schema

        return schema

    def run_transaction(self, script, write_collections,
            max_transaction_size=None, intermediate_commit_size=None, intermediate_commit_count=None,
            sync=True):
        """Execute JavaScript command in transaction against ArangoDB"""
        try:
            return self.db.execute_transaction(
                script,
                write=write_collections,
                sync=sync,
                allow_implicit=True,
                max_size=max_transaction_size,
                intermediate_commit_size=intermediate_commit_size,
                intermediate_commit_count=intermediate_commit_count
            )
        except TransactionExecuteError as e:
            return e

    def run_script(self, script, arangosh):
        """Execute JavaScript command through 'arangosh'"""
        command = [
            arangosh,
            '--server.endpoint', f'{self.protocol}://{self.host}:{self.port}',
            '--server.database', f'{self.db_name}',
            '--server.request-timeout', f'{self.timeout}'
        ]
        if self.username and self.password:
            command += [
                '--server.authentication', 'true',
                '--server.username', self.username,
                '--server.password', self.password,
            ]
        else:
            command += [
                '--server.authentication', 'false',
            ]
        command += [
            '--javascript.execute-string', f'({script})()'
        ]

        try:
            result = subprocess.run(command, text=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        except FileNotFoundError as e:
            return str(e)

        return result.stdout.replace('\\n', '\n')
