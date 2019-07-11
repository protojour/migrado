"""
migrado utility functions

Copyright © 2019 Protojour AS, licensed under MIT.
See LICENSE.txt for details.
"""

from pathlib import Path
import re


def ensure_path(path):
    """Ensure path given by `path` exists"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def select_migrations(current, target, migration_ids):
    """
    Select direction and migrations to run,
    given current and target migrations,
    from a list of migration ids
    """
    if target > current:
        return 'forward', [
            id_ for id_ in migration_ids
            if current < id_ <= target
        ]
    if target < current:
        return 'reverse', [
            id_ for id_ in reversed(migration_ids)
            if target < id_ <= current
        ]
    return None, []


def parse_write_collections(script):
    """Extract collections intended for writing from migration script"""
    collections_regex = r'//\s*write\s*([\w-]+)'
    return re.findall(collections_regex, script)


def extract_migration(script, name):
    """Extract given (forward, reverse) migration from script"""
    functions_regex = (
        r'.*(?P<forward>function forward.+{.+})' +
        r'.*(?P<reverse>function reverse.+{.+}).*'
    )
    matches = re.fullmatch(functions_regex, script, re.DOTALL)
    if matches and name in matches.groupdict():
        return matches.group(name)
