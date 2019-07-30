from pathlib import Path

import pytest

from migrado.utils import *


def test_ensure_path():
    path = Path('/tmp/migrado/test')

    assert not path.exists()
    assert not path.parent.exists()

    path = ensure_path('/tmp/migrado/test')

    assert path.exists()
    assert path.is_dir()

    path.rmdir()
    path.parent.rmdir()

    assert not path.exists()
    assert not path.parent.exists()


def test_select_migrations():
    migration_ids = ['0001', '0002', '0003']

    direction, selected = select_migrations('0000', '0003', migration_ids)
    assert direction == 'forward'
    assert selected == ['0001', '0002', '0003']

    direction, selected = select_migrations('0001', '0003', migration_ids)
    assert direction == 'forward'
    assert selected == ['0002', '0003']

    direction, selected = select_migrations('0003', '0001', migration_ids)
    assert direction == 'reverse'
    assert selected == ['0003', '0002']

    direction, selected = select_migrations('0001', '0002', migration_ids)
    assert direction == 'forward'
    assert selected == ['0002']

    direction, selected = select_migrations('0001', '0001', migration_ids)
    assert direction is None
    assert selected == []


def test_parse_write_collections():
    script = '''
    // write books
     // write authors
     //write author_of
    //write written-by
    this script has nothing more (interesting) in it
    '''

    write_collections = parse_write_collections(script)
    assert write_collections == ['books', 'authors', 'author_of', 'written-by']

    write_collections = parse_write_collections('')
    assert write_collections == []


def test_extract_migration():
    forward_function = \
    '''function forward() {
        var db = require("@arangodb").db
        if (innerBlock) {
            parsingStillWorks = true
        }
    }'''

    reverse_function = \
    '''function reverse (){
        // this is allowed ^
        var db = require("@arangodb").db
        // add your reverse migration here
    }'''

    script = '''
    test string please ignore
    {forward_function}
    also this
    {reverse_function}
    more garbage
    '''.format(
        forward_function=forward_function,
        reverse_function=reverse_function
    )

    forward_migration = extract_migration(script, 'forward')
    reverse_migration = extract_migration(script, 'reverse')

    assert forward_migration == forward_function
    assert reverse_migration == reverse_function

    script = f'''
    this script has nothing (interesting) in it
    '''

    forward_migration = extract_migration(script, 'forward')
    nothing_migration = extract_migration(script, 'nothing')

    assert forward_migration is None
    assert nothing_migration is None
