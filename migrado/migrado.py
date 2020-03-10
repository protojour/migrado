"""
migrado – ArangoDB migrations and batch processing manager

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

from pathlib import Path

import click
import yaml

from .constants import MIGRATION_TEMPLATE
from .db_client import MigrationClient
from .utils import (
    ensure_path, check_migrations, check_db, check_password,
    select_migrations, parse_write_collections, extract_migration
)


@click.group()
def migrado():
    """ArangoDB migrations and batch processing manager"""
    pass


path_option = click.option(
    '-p', '--path', type=click.Path(),
    default='migrations', show_default=True,
    envvar='MIGRADO_PATH', show_envvar=True,
    help='Specify path to migrations directory'
)
db_option = click.option('-d', '--db',
    envvar='MIGRADO_DB', show_envvar=True,
    help='Specify database name for migrations to interact with'
)
coll_option = click.option('-c', '--state-coll',
    default='migrado', show_default=True,
    envvar='MIGRADO_COLL', show_envvar=True,
    help='Specify collection name to store migration state in'
)
tls_option = click.option('-T', '--tls', is_flag=True,
    envvar='MIGRADO_TLS', show_envvar=True,
    help='Use TLS for connection when running migrations'
)
host_option = click.option('-H', '--host',
    default='localhost', show_default=True,
    envvar='MIGRADO_HOST', show_envvar=True,
    help='Specify database host to use for running migrations'
)
port_option = click.option('-P', '--port', type=int,
    default=8529, show_default=True,
    envvar='MIGRADO_PORT', show_envvar=True,
    help='Specify database port to use for running migrations'
)
user_option = click.option('-U', '--username',
    default='',
    envvar='MIGRADO_USER', show_envvar=True,
    help='Specify database username to use for running migrations'
)
pass_option = click.option('-W', '--password',
    default='',
    envvar='MIGRADO_PASS', show_envvar=True,
    help='Specify database password to use for running migrations. If only username is given, migrado will prompt for password.'
)
yes_option = click.option('-y', '--no-interaction', is_flag=True,
    help='Do not show interaction queries (assume \'yes\')'
)


@migrado.command()
@click.option(
    '-s', '--schema', type=click.File('r'),
    help='Build initial migration (collections) from YAML schema'
)
@path_option
def init(schema, path):
    """
    Build an initial migration.

    If no schema is provided, migrado will create the migrations directory
    and an empty initial migration.
    """
    migrations_path = ensure_path(path)
    initial_path = migrations_path.joinpath('0001_initial.js')

    if initial_path.exists():
        return click.echo('Initial migration already exists.')

    initial_data = MIGRATION_TEMPLATE
    forward_data = []
    reverse_data = []

    if schema:
        schema = yaml.safe_load(schema)
        for collection in schema.get('collections', {}).keys():
            forward_data.append(f'db._createDocumentCollection("{collection}")')
            reverse_data.append(f'db._drop("{collection}")')
        for collection in schema.get('edge_collections', {}).keys():
            forward_data.append(f'db._createEdgeCollection("{collection}")')
            reverse_data.append(f'db._drop("{collection}")')

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
    Inspect the current state of migrations
    """
    migrations_path = ensure_path(path)
    migrations = sorted(migrations_path.glob('[0-9]' * 4 + '*.js'))
    last_migration = migrations[-1]
    last_counter = last_migration.name[:4]

    check_migrations(migrations)
    check_db(db)

    password = check_password(username, password, no_interaction)

    client = MigrationClient(tls, host, port, username, password, db, state_coll)

    db_state = client.read_state()

    click.echo(f'Database migration state is at {db_state}.')
    click.echo(f'Latest migration on disk is {last_counter}.')


@migrado.command()
@click.option('-n', '--name',
    help='Give an optional name for the migration')
@path_option
def make(name, path):
    """
    Make a new, empty migration template.

    Will create a new template prefixed by the next available id, e.g. 0002.
    Migrations must be edited manually.
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
    migration_path.write_text(MIGRATION_TEMPLATE)
    migration_path.chmod(0o755)

    click.echo(f'New migration written to {migration_path} for your editing pleasure.')


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
@click.option('-I', '--docker-image',
    default='arangodb', show_default=True,
    envvar='MIGRADO_DOCKER_IMAGE', show_envvar=True,
    help='Specify Docker image name for container running migrations'
)
@click.option('-N', '--docker-network',
    default='host', show_default=True,
    envvar='MIGRADO_DOCKER_NETWORK', show_envvar=True,
    help='Specify Docker network name or mode for container running migrations'
)
@click.option('-S', '--docker-service',
    envvar='MIGRADO_DOCKER_SERVICE', show_envvar=True,
    help='Specify Docker service for running migrations against'
)
@click.option('--max-transaction-size', type=int,
    help='Specify RocksDB max transaction size in bytes'
)
@click.option('--intermediate-commit-size', type=int,
    help='Specify RocksDB transaction size in bytes before making intermediate commits'
)
@click.option('--intermediate-commit-count', type=int,
    help='Specify RocksDB transaction operation count before making intermediate commits'
)
@click.option('-a', '--arangosh', type=click.Path(),
    help='Use standalone arangosh from given path instead of Docker container'
)
@yes_option
def run(target, state, path,
        db, state_coll, tls, host, port, username, password,
        docker_image, docker_network, docker_service,
        max_transaction_size, intermediate_commit_size, intermediate_commit_count,
        arangosh, no_interaction):
    """
    Run all migrations or migrate to a specific target.

    migrado will check the configured database for migration metadata.

    If no target is specified, migrado will run all migrations that have not
    been applied in sequence.

    If a target is specified, migrado will run all migrations between the current
    state and the given state. If the given state is behind the current, reverse
    migrations are employed.

    The new state is written as metadata to the configured database
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

    client = MigrationClient(tls, host, port, username, password, db, state_coll)

    state = state or client.read_state()

    direction, migration_ids = select_migrations(state, target, migration_ids)

    for id_ in migration_ids:
        script = migrations_dict[id_].read_text()
        write_collections = parse_write_collections(script)
        migration = extract_migration(script, direction)

        click.echo(f'Running {direction} migration {id_} in transaction...')
        error = client.run_transaction(migration, write_collections,
            max_transaction_size, intermediate_commit_size, intermediate_commit_count)

        if error:
            click.echo('Error! %s' % error)

            method = 'through arangosh' if arangosh else 'in Docker container'
            if not no_interaction:
                click.confirm(f'Run migration {method}?', abort=True)

            click.echo(f'Running {direction} migration {id_} {method}...')
            error = client.run_script(migration, arangosh, docker_image, docker_network, docker_service)

            if error:
                click.echo('Error! arangosh says:')
                click.echo(error)
                raise click.Abort()

        client.write_state(id_)
        click.echo(f'State is now at {id_}.')

    click.echo('Done.')
