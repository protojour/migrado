import os

import pytest
from arango.exceptions import *

from .conftest import clean_arango
from migrado.db_client import MigrationClient


TLS = os.getenv('MIGRADO_TLS', False) in ['True', 'true', '1']
HOST = os.getenv('MIGRADO_HOST', 'localhost')
PORT = int(os.getenv('MIGRADO_PORT', 8529))
USERNAME = os.getenv('MIGRADO_USER', '')
PASSWORD = os.getenv('MIGRADO_PASS', '')
DB = os.getenv('MIGRADO_DB', 'test')
COLL = os.getenv('MIGRADO_STATE_COLL', 'migrado')
DOCKER_IMAGE = os.getenv('MIGRADO_DOCKER_IMAGE', 'arangodb')
DOCKER_NETWORK = os.getenv('MIGRADO_DOCKER_NETWORK', 'migrado_default')
DOCKER_SERVICE = os.getenv('MIGRADO_DOCKER_SERVICE', 'arangodb')


def test_migration_client(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    client_two = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)

    with pytest.raises(ServerConnectionError):
        client_inacessible = \
            MigrationClient(TLS, 'inaccessible', PORT, USERNAME, PASSWORD, DB, COLL)


def test_read_write_state(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)
    current = client.read_state()

    assert current == '0000'

    success = client.write_state('0001')
    current = client.read_state()

    assert success
    assert current == '0001'


def test_run_transaction(clean_arango):

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)

    error = client.run_transaction(None, None)
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

    client = MigrationClient(TLS, HOST, PORT, USERNAME, PASSWORD, DB, COLL)

    output = client.run_script(None, DOCKER_IMAGE, DOCKER_NETWORK, DOCKER_SERVICE)
    assert 'None is not defined' in output

    output = client.run_script('', DOCKER_IMAGE, DOCKER_NETWORK, DOCKER_SERVICE)
    assert 'Unexpected token' in output

    assert not client.db.has_collection('things')

    valid_function = '''
    function forward() {
        var db = require("@arangodb").db
        db._createDocumentCollection("things")
    }
    '''

    output = client.run_script(valid_function, DOCKER_IMAGE, DOCKER_NETWORK, DOCKER_SERVICE)
    assert output == ''
    assert client.db.has_collection('things')
