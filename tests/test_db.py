import os

import pytest
from arango.exceptions import *

from .conftest import clean_arango
from migrado.db_client import MigrationClient


def test_migration_client(clean_arango):

    host = os.getenv('MIGRADO_HOST', 'localhost')
    port = os.getenv('MIGRADO_PORT', 8529)
    db = os.getenv('MIGRADO_DB', 'test')
    coll = os.getenv('MIGRADO_STATE_COLL', 'migrado')

    client = MigrationClient(host, port, db, coll)
    client_two = MigrationClient(host, port, db, coll)

    with pytest.raises(ServerConnectionError):
        client_inacessible = \
            MigrationClient('inaccessible', port, db, coll)


def test_read_write_state(clean_arango):

    host = os.getenv('MIGRADO_HOST', 'localhost')
    port = os.getenv('MIGRADO_PORT', 8529)
    db = os.getenv('MIGRADO_DB', 'test')
    coll = os.getenv('MIGRADO_STATE_COLL', 'migrado')

    client = MigrationClient(host, port, db, coll)
    current = client.read_state()

    assert current == '0000'

    success = client.write_state('0001')
    current = client.read_state()

    assert success
    assert current == '0001'


def test_run_transaction(clean_arango):

    host = os.getenv('MIGRADO_HOST', 'localhost')
    port = os.getenv('MIGRADO_PORT', 8529)
    db = os.getenv('MIGRADO_DB', 'test')
    coll = os.getenv('MIGRADO_STATE_COLL', 'migrado')

    client = MigrationClient(host, port, db, coll)

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

    host = os.getenv('MIGRADO_HOST', 'localhost')
    port = os.getenv('MIGRADO_PORT', 8529)
    db = os.getenv('MIGRADO_DB', 'test')
    coll = os.getenv('MIGRADO_STATE_COLL', 'migrado')

    docker_image = 'arangodb'
    docker_network = 'migrado_default'
    docker_service = 'arangodb'

    client = MigrationClient(host, port, db, coll)

    output = client.run_script(None, docker_image, docker_network, docker_service)
    assert 'None is not defined' in output

    output = client.run_script('', docker_image, docker_network, docker_service)
    assert 'Unexpected token' in output

    assert not client.db.has_collection('things')

    valid_function = '''
    function forward() {
        var db = require("@arangodb").db
        db._createDocumentCollection("things")
    }
    '''

    output = client.run_script(valid_function, docker_image, docker_network, docker_service)
    assert output == ''
    assert client.db.has_collection('things')
