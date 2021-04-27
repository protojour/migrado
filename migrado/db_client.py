"""
migrado database client

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

import subprocess

from arango import ArangoClient
from arango.exceptions import *


class MigrationClient:
    """Client for reading and writing state, running migrations against ArangoDB"""

    def __init__(self, tls, host, port, username, password, db, coll):
        self.protocol = 'https' if tls else 'http'
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db
        self.coll_name = coll

        self.db_client = ArangoClient(f'{self.protocol}://{host}:{port}')

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
            state = {
                '_key': 'state',
                'migration_id': '0000',
            }

        return state.get('migration_id')

    def write_state(self, migration_id):
        """Write given state to state collection"""
        state = {
            '_key': 'state',
            'migration_id': migration_id,
        }
        return self.state_coll.insert(state, overwrite=True, silent=True)

    def run_transaction(self, script, write_collections,
                        max_transaction_size=None, intermediate_commit_size=None, intermediate_commit_count=None):
        """Execute JavaScript command in transaction against ArangoDB"""
        try:
            return self.db.execute_transaction(
                script,
                write=write_collections,
                sync=True,
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
            '--server.database', f'{self.db_name}'
        ]
        if self.username and self.password:
            command += [
                '--server.authentication', 'true'
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
