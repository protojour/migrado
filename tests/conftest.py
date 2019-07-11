import os

import pytest
from click.testing import CliRunner
from arango import ArangoClient


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def clean_arango():
    host = os.getenv('MIGRADO_HOST', 'localhost')
    port = os.getenv('MIGRADO_PORT', 8529)
    db_name = os.getenv('MIGRADO_DB', 'test')

    client = ArangoClient(host=host, port=port)
    sys_db = client.db('_system')

    if sys_db.has_database(db_name):
        sys_db.delete_database(db_name)
        sys_db.create_database(db_name)
    else:
        sys_db.create_database(db_name)

    return client
