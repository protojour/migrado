"""
Migrado – ArangoDB migrations and batch processing manager

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

import json

import click
import yaml

from .constants import MIGRATION_TEMPLATE
from .db_client import MigrationClient
from .utils import (
    ensure_path, check_migrations, check_db, check_password,
    select_migrations, parse_write_collections,
    extract_migration, extract_schema, get_options
)


path_option = click.option(
    '-p', '--path', type=click.Path(),
    default='migrations', show_default=True,
    envvar='MIGRADO_PATH', show_envvar=True,
    help='Specify path to migrations directory'
)
db_option = click.option(
    '-d', '--db',
    envvar='MIGRADO_DB', show_envvar=True,
    help='Specify database name for migrations to interact with'
)
coll_option = click.option(
    '-c', '--state-coll',
    default='migrado', show_default=True,
    envvar='MIGRADO_COLL', show_envvar=True,
    help='Specify collection name to store migration state in'
)
tls_option = click.option(
    '-T', '--tls', is_flag=True,
    envvar='MIGRADO_TLS', show_envvar=True,
    help='Use TLS for connection when running migrations'
)
host_option = click.option(
    '-H', '--host',
    default='localhost', show_default=True,
    envvar='MIGRADO_HOST', show_envvar=True,
    help='Specify database host to use for running migrations'
)
port_option = click.option(
    '-P', '--port', type=int,
    default=8529, show_default=True,
    envvar='MIGRADO_PORT', show_envvar=True,
    help='Specify database port to use for running migrations'
)
user_option = click.option(
    '-U', '--username',
    default='',
    envvar='MIGRADO_USER', show_envvar=True,
    help='Specify database username to use for running migrations'
)
pass_option = click.option(
    '-W', '--password',
    default='',
    envvar='MIGRADO_PASS', show_envvar=True,
    help=('Specify database password to use for running migrations. If only username is given, ' +
    'Migrado will prompt for password.')
)
timeout_option = click.option(
    '--timeout', type=int,
    default=1200, show_default=True,
    help='Request timeout in seconds'
)
validation_option = click.option(
    '-v', '--validation',
    type=click.Choice(['none', 'new', 'moderate', 'strict']),
    help='Write collection validation rules from YAML schema at given level'
)
yes_option = click.option(
    '-y', '--no-interaction', is_flag=True,
    help='Do not show interaction queries (assume \'yes\')'
)


class NaturalOrderGroup(click.Group):
    """Group to show commands in their specified order"""

    def list_commands(self, ctx):
        return self.commands.keys()


@click.group(cls=NaturalOrderGroup)
def migrado():
    """ArangoDB migrations and batch processing manager"""
    pass


@migrado.command()
@click.option(
    '-s', '--schema',
    type=click.File('r'),
    help='Build initial schema migration from YAML schema'
)
@click.option(
    '-i', '--infer', is_flag=True,
    help='Infer initial schema from current database structure'
)
@validation_option
@path_option
@db_option
@coll_option
@tls_option
@host_option
@port_option
@user_option
@pass_option
@yes_option
def init(schema, infer, validation, path,
        db, state_coll, tls, host, port, username, password, no_interaction):
    """
    Build an initial migration.

    Migrado will create the migrations directory and an initial migration.
    This can be generated from a schema (-s/--schema) or inferred from current
    database structure (-i/--infer).

    If neither option is used, Migrado will generate an empty initial migration.
    """
    migrations_path = ensure_path(path)
    initial_path = migrations_path.joinpath('0001_initial.js')

    if initial_path.exists():
        return click.echo('Initial migration already exists.')

    initial_data = MIGRATION_TEMPLATE
    forward_data = []
    reverse_data = []

    if infer:
        check_db(db)
        password = check_password(username, password, no_interaction)
        db_client = MigrationClient(tls, host, port, username, password, db, state_coll)
        schema = db_client.infer_schema(validation)

        if schema['collections'] or schema['edge_collections']:
            db_client.write_state('0001')
            click.echo(f'State is now at 0001.')
            db_client.write_schema(schema)
            click.echo('Schema stored in database.')

    if schema:
        if not isinstance(schema, dict):
            schema = yaml.safe_load(schema)

        schema = {
            'collections': schema.get('collections', {}),
            'edge_collections': schema.get('edge_collections', {})
        }
        forward_data.append(f'var schema = {json.dumps(schema)}')

        for name, props in schema.get('collections', {}).items():
            options = get_options(props, validation)
            forward_data.append(f'db._create("{name}", {json.dumps(options)})')
            reverse_data.append(f'db._drop("{name}")')

        for name, props in schema.get('edge_collections', {}).items():
            options = get_options(props, validation)
            forward_data.append(f'db._create("{name}", {json.dumps(options)}, "edge")')
            reverse_data.append(f'db._drop("{name}")')

    if forward_data:
        initial_data = initial_data.replace(
            '// add your forward migration here',
            '\n    '.join(forward_data)
        )

    if reverse_data:
        initial_data = initial_data.replace(
            '// add your reverse migration here',
            '\n    '.join(reverse_data)
        )

    initial_path.write_text(initial_data)
    initial_path.chmod(0o755)

    click.echo(f'Initial migration written to {initial_path}.')


@migrado.command()
@path_option
@db_option
@coll_option
@tls_option
@host_option
@port_option
@user_option
@pass_option
@yes_option
def inspect(path, db, state_coll, tls, host, port, username, password, no_interaction):
    """
    Inspect the current state of migrations.
    """
    migrations_path = ensure_path(path)
    migrations = sorted(migrations_path.glob('[0-9]' * 4 + '*.js'))
    last_migration = migrations[-1]
    last_counter = last_migration.name[:4]

    check_migrations(migrations)
    check_db(db)
    password = check_password(username, password, no_interaction)

    db_client = MigrationClient(tls, host, port, username, password, db, state_coll)
    db_state = db_client.read_state()

    click.echo(f'Database migration state is at {db_state}.')
    click.echo(f'Latest migration on disk is {last_counter}.')


@migrado.command()
@click.argument('filename', type=click.File('w'), required=False)
@validation_option
@db_option
@coll_option
@tls_option
@host_option
@port_option
@user_option
@pass_option
@yes_option
def export(filename, validation, db, state_coll, tls, host, port, username, password, no_interaction):
    """
    Export or infer current database schema.

    If no database schema is found, Migrado will infer schema from current database
    structure

    Outputs to stdout if no filename is given.
    """
    check_db(db)
    password = check_password(username, password, no_interaction)

    db_client = MigrationClient(tls, host, port, username, password, db, state_coll)
    db_schema = db_client.read_schema()

    if not db_schema:
        db_schema = db_client.infer_schema(validation)

    schema = yaml.safe_dump(db_schema, sort_keys=False)

    if filename:
        filename.write(schema)
    else:
        click.echo(schema)


@migrado.command()
@click.option(
    '-n', '--name',
    help='Give an optional name for the migration'
)
@click.option(
    '-s', '--schema',
    type=click.File('r'),
    help='Build schema migration diff from updated YAML schema'
)
@validation_option
@path_option
@db_option
@coll_option
@tls_option
@host_option
@port_option
@user_option
@pass_option
@yes_option
def make(name, schema, validation,
        path, db, state_coll, tls, host, port, username, password, no_interaction):
    """
    Make a new migration template or generate schema migration.

    Migration will be prefixed by the next available migration id, e.g. 0002.
    Non-schema migrations must be edited manually.
    """

    migrations_path = ensure_path(path)
    migrations = sorted(migrations_path.glob('[0-9]' * 4 + '*.js'))

    check_migrations(migrations)

    last_migration = migrations[-1]
    last_counter = last_migration.name[:4]
    counter = str(int(last_counter) + 1).zfill(4)

    filename = f'{counter}.js'
    if name:
        filename = f'{counter}_{name}.js'

    migration_path = migrations_path.joinpath(filename)

    initial_data = MIGRATION_TEMPLATE
    forward_data = []
    reverse_data = []

    if schema:
        check_db(db)
        password = check_password(username, password, no_interaction)

        db_client = MigrationClient(tls, host, port, username, password, db, state_coll)
        db_schema = db_client.read_schema()

        if not db_schema:
            click.echo('Inferring schema from current database structure.')
            db_schema = db_client.infer_schema(validation)

        schema = yaml.safe_load(schema)
        schema = {
            'collections': schema.get('collections', {}),
            'edge_collections': schema.get('edge_collections', {})
        }
        forward_data.append(f'var schema = {json.dumps(schema)}')
        reverse_data.append(f'var schema = {json.dumps(db_schema)}')

        new_collections = {
            collection: props for collection, props in schema['collections'].items()
            if collection not in db_schema['collections']
        }
        new_edge_collections = {
            collection: props for collection, props in schema['edge_collections'].items()
            if collection not in db_schema['edge_collections']
        }

        updated_collections = {
            collection: props for collection, props in schema['collections'].items()
            if collection in db_schema['collections']
        }
        updated_edge_collections = {
            collection: props for collection, props in schema['edge_collections'].items()
            if collection in db_schema['edge_collections']
        }

        removed_collections = {
            collection: props for collection, props in db_schema['collections'].items()
            if collection not in schema['collections']
        }
        removed_edge_collections = {
            collection: props for collection, props in db_schema['edge_collections'].items()
            if collection not in schema['edge_collections']
        }

        for name, props in new_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db._create("{name}", {json.dumps(options)})')
            reverse_data.append(f'db._drop("{name}")')

        for name, props in new_edge_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db._create("{name}", {json.dumps(options)}, "edge")')
            reverse_data.append(f'db._drop("{name}")')

        for name, props in updated_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db.{name}.properties({json.dumps(options)})')
            options = get_options(db_schema['collections'].get(name, {}), validation)
            reverse_data.append(f'db.{name}.properties({json.dumps(options)})')

        for name, props in updated_edge_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db.{name}.properties({json.dumps(options)})')
            options = get_options(db_schema['edge_collections'].get(name, {}), validation)
            reverse_data.append(f'db.{name}.properties({json.dumps(options)})')

        for name, props in removed_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db._drop("{name}")')
            reverse_data.append(f'db._create("{name}", {json.dumps(options)})')

        for name, props in removed_edge_collections.items():
            options = get_options(props, validation)
            forward_data.append(f'db._drop("{name}")')
            reverse_data.append(f'db._create("{name}", {json.dumps(options)}, "edge")')

        if forward_data:
            initial_data = initial_data.replace(
                '// add your forward migration here',
                '\n    '.join(forward_data)
            )

        if reverse_data:
            initial_data = initial_data.replace(
                '// add your reverse migration here',
                '\n    '.join(reverse_data)
            )

    migration_path.write_text(initial_data)
    migration_path.chmod(0o755)

    if schema:
        click.echo(f'Schema migration written to {migration_path}.')
    else:
        click.echo(f'New migration template written to {migration_path} for your editing pleasure.')


@migrado.command()
@click.option(
    '-t', '--target',
    help='Specify a four-digit target migration id'
)
@click.option(
    '-s', '--state',
    help='Override current state migration id'
)
@path_option
@db_option
@coll_option
@tls_option
@host_option
@port_option
@user_option
@pass_option
@click.option(
    '--max-transaction-size', type=int,
    help='Specify RocksDB max transaction size in bytes'
)
@click.option(
    '--intermediate-commit-size', type=int,
    help='Specify RocksDB transaction size in bytes before making intermediate commits'
)
@click.option(
    '--intermediate-commit-count', type=int,
    help='Specify RocksDB transaction operation count before making intermediate commits'
)
@timeout_option
@click.option(
    '--async', 'async_', is_flag=True,
    help='Run transactions asynchronously'
)
@click.option(
    '-a', '--arangosh', type=click.Path(),
    default='arangosh', help='Use arangosh from given path'
)
@yes_option
def run(target, state,
        path, db, state_coll, tls, host, port, username, password,
        max_transaction_size, intermediate_commit_size, intermediate_commit_count,
        timeout, async_, arangosh, no_interaction):
    """
    Run all migrations, or migrate to a specific target.

    Migrado will check the configured database for migration metadata.

    If no target is specified, Migrado will run all migrations that have not
    been applied, in sequence.

    If a target is specified, Migrado will run all migrations between the current
    state and the given state. If the given state is behind the current, reverse
    migrations are employed.

    State and schemas are written as metadata to the configured database
    (see --db, --state-coll).
    """
    migrations_path = ensure_path(path)
    migrations = sorted(migrations_path.glob('[0-9]' * 4 + '*.js'))
    migrations_dict = {migration.name[:4]: migration for migration in migrations}
    migration_ids = [id_ for id_ in migrations_dict]

    check_migrations(migrations)
    check_db(db)

    target = target or migration_ids[-1]
    if target not in migration_ids:
        raise click.UsageError(f'Target {target} not found, please specify a four-digit migration id.')

    password = check_password(username, password, no_interaction)

    db_client = MigrationClient(tls, host, port, username, password, db, state_coll, timeout)

    try:
        state = state or db_client.read_state()
    except Exception as error:
        click.echo('Error! %s' % error)
        raise click.Abort()

    direction, migration_ids = select_migrations(state, target, migration_ids)

    for id_ in migration_ids:
        script = migrations_dict[id_].read_text()
        write_collections = parse_write_collections(script)
        migration = extract_migration(script, direction)

        click.echo(f'Running {direction} migration {id_} in transaction...')
        error = db_client.run_transaction(migration, write_collections,
            max_transaction_size, intermediate_commit_size, intermediate_commit_count,
            not async_
        )

        if error:
            click.echo('Error! %s' % error)

            click.echo(f'Running {direction} migration {id_} as schema migration...')
            error = db_client.run_script(migration, arangosh)

            if error:
                click.echo('Error! %s' % error)
                raise click.Abort()

            schema = extract_schema(script)
            if schema:
                db_client.write_schema(schema)
                click.echo('Schema stored in database.')

        db_client.write_state(id_)
        click.echo(f'State is now at {id_}.')

    click.echo('Done.')
