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
    ensure_path, select_migrations, parse_write_collections, extract_migration
)


@click.group()
def migrado():
    """ArangoDB migrations and batch processing manager"""
    pass


path_option = click.option('-p', '--path', type=click.Path(),
    default='migrations', show_default=True,
    envvar='MIGRADO_PATH',
    help='Specify path to migrations directory')
db_option = click.option('-d', '--db',
    envvar='MIGRADO_DB',
    help='Specify database name for migrations to interact with')
coll_option = click.option('-c', '--state-coll',
    default='migrado', show_default=True,
    envvar='MIGRADO_COLL',
    help='Specify collection name to store migration state in')
host_option = click.option('-H', '--host',
    default='localhost', show_default=True,
    envvar='MIGRADO_HOST',
    help='Specify database host to use for running migrations')
port_option = click.option('-P', '--port',
    default=8529, show_default=True,
    envvar='MIGRADO_PORT',
    help='Specify database port to use for running migrations')
image_option = click.option('-I', '--docker-image',
    default='arangodb', show_default=True,
    envvar='MIGRADO_DOCKER_IMAGE',
    help='Specify Docker image name for container running migrations')
network_option = click.option('-N', '--docker-network',
    default='host', show_default=True,
    envvar='MIGRADO_DOCKER_NETWORK',
    help='Specify Docker network name or mode for container running migrations')
service_option = click.option('-S', '--docker-service',
    envvar='MIGRADO_DOCKER_SERVICE',
    help='Specify Docker service for running migrations against')


@migrado.command()
@click.option('-s', '--schema', type=click.File('r'),
    help='Build initial migration (collections) from YAML schema')
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
        return print('Initial migration already exists.')

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

    print(f'Initial migration written to {initial_path}.')


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

    if not migrations:
        raise click.UsageError('No migrations found, run migrado init')

    last_migration = migrations[-1]
    last_counter = last_migration.name[:4]
    counter = str(int(last_counter) + 1).zfill(4)

    filename = f'{counter}.js'
    if name:
        filename = f'{counter}_{name}.js'

    migration_path = migrations_path.joinpath(filename)
    migration_path.write_text(MIGRATION_TEMPLATE)
    migration_path.chmod(0o755)

    print(f'New migration written to {migration_path} for your editing pleasure.')


@migrado.command()
@click.option('-t', '--target',
    help='Specify a four-digit target migration id')
@click.option('-s', '--state',
    help='Override current state migration id')
@path_option
@db_option
@coll_option
@host_option
@port_option
@image_option
@network_option
@service_option
@click.option('-y', '--no-interaction', is_flag=True,
    help="Answer yes to all confirmation queries")
def run(target, state, path,
        db, state_coll, host, port,
        docker_image, docker_network, docker_service,
        no_interaction):
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

    if not migrations:
        raise click.UsageError('No migrations found, run migrado init')

    target = target or migration_ids[-1]
    if target not in migration_ids:
        raise click.UsageError(f'Target {target} not found, please specify a four-digit migration id.')

    if not db:
        raise click.UsageError('Database name not specified, use --db or MIGRADO_DB')

    client = MigrationClient(host, port, db, state_coll)
    state = state or client.read_state()

    direction, migration_ids = select_migrations(state, target, migration_ids)

    for id_ in migration_ids:
        script = migrations_dict[id_].read_text()
        write_collections = parse_write_collections(script)
        migration = extract_migration(script, direction)

        print(f'Running {direction} migration {id_} in transaction...')
        error = client.run_transaction(migration, write_collections)

        if error:
            print('Error!', error)

            if not no_interaction:
                click.confirm('Run in Docker container?', abort=True)

            print(f'Running {direction} migration {id_} in container...')
            logs = client.run_script(migration, docker_image, docker_network, docker_service)

            if logs:
                print('Error! Container says:')
                print(logs)
                raise click.Abort()

        client.write_state(id_)
        print(f'State is now at {id_}.')

    print('Done.')
