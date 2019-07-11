import os
from pathlib import Path

import pytest

from .conftest import runner, clean_arango
from migrado import migrado, __version__
from migrado.constants import MIGRATION_TEMPLATE


def test_version():
    assert __version__ == '0.1.0'


def test_migrado(runner):
    result = runner.invoke(migrado)
    assert result.exit_code == 0


def test_migrado_init(runner):
    with runner.isolated_filesystem():

        result = runner.invoke(migrado, ['init'])
        assert result.exit_code == 0
        assert 'Initial migration written' in result.output
        assert Path('migrations').exists()
        assert Path('migrations/0001_initial.js').exists()

        # with Path('migrations/0001_initial.js').open('r') as f:
        #     content = f.read()
        #     assert 'db._createDatabase("test")' in content
        #     assert 'db._useDatabase("test")' in content

        result = runner.invoke(migrado, ['init'])
        assert result.exit_code == 0
        assert 'Initial migration already exists' in result.output

        result = runner.invoke(migrado, ['init', '--path', 'migrados'])
        assert result.exit_code == 0
        assert 'Initial migration written' in result.output
        assert Path('migrados').exists()
        assert Path('migrados/0001_initial.js').exists()


def test_migrado_init_schema(runner):
    schema_path = Path('tests/test_schema.yml').resolve()
    with runner.isolated_filesystem():

        result = runner.invoke(migrado, ['init', '--schema', schema_path])
        assert result.exit_code == 0
        assert Path('migrations').exists()
        assert Path('migrations/0001_initial.js').exists()

        with Path('migrations/0001_initial.js').open('r') as f:
            content = f.read()
            assert 'db._createDocumentCollection("books")' in content
            assert 'db._createDocumentCollection("authors")' in content
            assert 'db._createEdgeCollection("author_of")' in content
            assert content.index('db._createEdgeCollection("author_of")') > content.index('forward()')
            assert content.index('db._createEdgeCollection("author_of")') < content.index('reverse()')

            assert 'db._drop("books")' in content
            assert 'db._drop("authors")' in content
            assert 'db._drop("author_of")' in content
            assert content.index('db._drop("author_of")') > content.index('reverse()')
            assert content.index('db._drop("author_of")') < content.index('forward() // default')


def test_migrado_make(runner):
    with runner.isolated_filesystem():

        result = runner.invoke(migrado, ['make'])
        assert result.exit_code == 2
        assert 'No migrations found' in result.output

        result = runner.invoke(migrado, ['init'])
        assert result.exit_code == 0

        result = runner.invoke(migrado, ['make'])
        assert result.exit_code == 0
        assert 'New migration written' in result.output
        assert Path('migrations/0002.js').exists()

        result = runner.invoke(migrado, ['make', '--name', 'test'])
        assert result.exit_code == 0
        assert 'New migration written' in result.output
        assert Path('migrations/0003_test.js').exists()

        with Path('migrations/0003_test.js').open('r') as f:
            content = f.read()
            assert MIGRATION_TEMPLATE in content


def test_migrado_run(runner, clean_arango):
    schema_path = Path('tests/test_schema.yml').resolve()
    with runner.isolated_filesystem():

        result = runner.invoke(migrado, ['run'])
        assert result.exit_code == 2
        assert 'No migrations found' in result.output

        result = runner.invoke(migrado, ['init', '--schema', schema_path])
        assert result.exit_code == 0

        result = runner.invoke(migrado, ['run', '--target', '0002'])
        assert result.exit_code == 2
        assert 'Target 0002 not found' in result.output

        result = runner.invoke(migrado, ['run', '--db', ''])
        assert result.exit_code == 2
        assert 'Database name not specified' in result.output

        result = runner.invoke(migrado, ['run', '--no-interaction'])
        assert result.exit_code == 1
        assert 'Error!' in result.output
        assert 'not connected' in result.output

        result = runner.invoke(migrado, ['run', '--docker-network', 'migrado_default', '--docker-service', 'arangodb'], input='y\n')
        assert result.exit_code == 0
        assert 'State is now at 0001.' in result.output
        assert 'Done.' in result.output
