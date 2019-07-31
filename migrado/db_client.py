"""
migrado database client

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

from arango import ArangoClient
from arango.exceptions import *
import docker


class MigrationClient:
    """
    Client for reading and writing state, running migrations
    against ArangoDB
    """

    def __init__(self, tls, host, port, username, password, db, coll):
        self.protocol = 'https' if tls else 'http'
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db
        self.coll_name = coll

        self.db_client = ArangoClient(protocol=self.protocol, host=host, port=port)
        self.docker_client = docker.from_env()

        self.sys_db = self.db_client.db(
            name='_system',
            username=username,
            password=password,
            verify=True
        )

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

    def run_transaction(self, script, write_collections):
        """Execute JavaScript command in transaction against ArangoDB"""
        try:
            return self.db.execute_transaction(
                script,
                write=write_collections,
                sync=True,
                allow_implicit=True
            )
        except TransactionExecuteError as e:
            return e

    def run_script(self, script, docker_image, docker_network, docker_service):
        """Execute JavaScript command through 'arangosh' in Docker container"""
        host = docker_service or self.host
        command = '''arangosh \\
        --server.endpoint {protocol}://{host}:{port} \\
        --server.database {db_name} \\
        --server.authentication false \\
        --javascript.execute-string '({script})()'
        '''.format(
            protocol=self.protocol,
            host=host,
            port=self.port,
            db_name=self.db_name,
            script=script
        )
        if self.username and self.password:
            auth = '''
            --server.authentication true \\
            --server.username {username} \\
            --server.password {password} \\
            '''.format(
                username=self.username,
                password=self.password
            )
            command = command.replace(
                '--server.authentication false \\',
                auth
            )
        container = self.docker_client.containers.run(
            image=docker_image,
            command=command,
            network_mode=docker_network,
            detach=True
        )
        container.wait()
        return container.logs().decode('utf-8').replace('\\n', '\n')
