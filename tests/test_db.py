import os

import pytest
from arango.exceptions import *

from migrado.db_client import MigrationClient


TLS = os.getenv('MIGRADO_TLS', False) in ['True', 'true', '1']
HOST = os.getenv('MIGRADO_HOST', 'localhost')
PORT = int(os.getenv('MIGRADO_PORT', 8529))
USERNAME = os.getenv('MIGRADO_USER', '')
PASSWORD = os.getenv('MIGRADO_PASS', '')
DB = os.getenv('MIGRADO_DB', 'test')
COLL = os.getenv('MIGRADO_STATE_COLL', 'migrado')


def test_migration_client(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    client_two = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)


def test_read_write_state(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    current = client.read_state()

    assert current == '0000'

    success = client.write_state('0001')
    current = client.read_state()

    assert success
    assert current == '0001'


def test_read_write_schema(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    current = client.read_schema()

    assert current == {}

    success = client.write_schema({"test": "schema"})
    current = client.read_schema()

    assert success
    assert current == {"test": "schema"}


def test_infer_schema(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    schema = client.infer_schema(validation=False)

    assert schema == {
        'collections': {},
        'edge_collections': {}
    }

    collection_schema = {
        'rule': {
            'properties': {
                'test': {
                    'type': 'string'
                }
            }
        },
        'level': 'strict',
        'message': 'Test message'
    }
    client.db.create_collection('things', schema=collection_schema)
    client.db.create_collection('stuff')
    client.db.create_collection('has_stuff', edge=True, schema=collection_schema)

    schema = client.infer_schema(validation=False)

    assert schema == {
        'collections': {
            'things': None,
            'stuff': None
        },
        'edge_collections': {
            'has_stuff': None
        }
    }

    schema = client.infer_schema(validation=True)

    assert schema == {
        'collections': {
            'things': {
                'schema': collection_schema
            },
            'stuff': None
        },
        'edge_collections': {
            'has_stuff': {
                'schema': collection_schema
            }
        }
    }


def test_run_transaction(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)

    error = client.run_transaction(None, None,)
    assert error

    error = client.run_transaction('', [])
    assert error

    valid_function = '''
    function forward() {
        var db = require("@arangodb").db
        db._query(`
            FOR state IN migrado
                UPDATE state WITH { migration_id: "9999" } IN migrado
        `)
    }
    '''

    # does not declare write collections
    error = client.run_transaction(valid_function, [])
    assert error

    assert client.write_state('0000')
    assert client.read_state() == '0000'

    # does declare migrations
    error = client.run_transaction(valid_function, ['migrado'])
    assert not error
    assert client.read_state() == '9999'


def test_run_script(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, 'test', 'hunter2', DB, COLL)

    output = client.run_script(None, 'arangosh')
    assert 'None is not defined' in output

    output = client.run_script('', 'arangosh')
    assert 'Unexpected token' in output

    assert not client.db.has_collection('things')

    valid_function = '''
    function forward() {
        var db = require("@arangodb").db
        db._create("things")
    }
    '''

    output = client.run_script(valid_function, 'arangosh')
    assert output == ''
    assert client.db.has_collection('things')
