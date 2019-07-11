migrado
=======

![PyPI package](https://badge.fury.io/py/migrado.svg)
![Build status](https://travis-ci.org/protojour/migrado.svg?branch=master)

🥑 ArangoDB migrations and batch processing manager.

migrado is a command-line client that can help build and run schema or data migrations against your ArangoDB instance. 

migrado utilizes ArangoDB Transactions when running data migrations to ensure failed scripts are rolled back automatically. [Docker](https://docs.docker.com/install/) is required to run schema migrations, however no transaction safety is available at this point.

**migrado should be considered alpha software.** Make sure you test well before using in a production setting.

If you have trouble, open an issue. Contributions are welcome.

Installation
------------

```bash
$ pip install --user migrado
```

Usage
-----

migrado can create a migrations directory and generate an initial set of collections from the given schema file:

```bash
$ migrado init --schema schema.yml
```

See [YAML schemas](#yaml-schemas) for details. If no schema is specified, migrado will create an empty initial migration.

To make a new template migration script:

```bash
$ migrado make --name rewrite_names
```

This will create a new file, `migrations/0002_rewrite_names.js` (`--name` is optional), which you can edit as you see fit. See [Migration scripts](#migration-scripts) for details.

When you are ready, run all migrations not currently ran against the database: 

```bash
$ migrado run
```

migrado stores migration state in a configurable collection, see `--help` or [Environment vars](#environment-vars) for details.

If you wrote a `reverse()` migration, you can revert to an earlier point by specifying a target migration id. To revert to the initial migration:

```bash
$ migrado run --target 0001
```

Use the `--help` option for help on any command when using the client.

Environment vars
----------------

The following environment variables are employed by migrado:

- `MIGRADO_PATH`: Specifies the path to the migrations directory, replaces `-p`, `--path` (default: `migrations`).
- `MIGRADO_DB`: Specifies the ArangoDB database name for generated migrations to interact with, replaces `-d`, `--db` (no default, but required for the `run` command).
- `MIGRADO_COLL`: Specifies ArangoDb collection name to store migration state in, replaces `-c`, `--state-coll` (default: `migrado`).
- `MIGRADO_HOST`: Specifies the database host for running migrations, replaces `-H`, `--host` (default: `localhost`).
- `MIGRADO_PORT`: Specifies the database port for running migrations, replaces `-P`, `--port` (default: `8529`).
- `MIGRADO_DOCKER_IMAGE`: Specifies the Docker image (and optionally tag) for the container running migrations, replaces `-I`, `--docker-image` (default: `arangodb`).
- `MIGRADO_DOCKER_NETWORK`: Specifies a Docker network mode or name for running migrations, replaces `-N`, `--docker-network`. Valid values are `host` (default, use the host network), or any network name.
- `MIGRADO_DOCKER_SERVICE`: Specifies a Docker service to connect to when running migrations, replaces `-S`, `--docker-service` (default: same value as `MIGRADO_HOST`).

If your ArangoDB instance is itself running on Docker, `MIGRADO_DOCKER_NETWORK` and `MIGRADO_DOCKER_SERVICE` may be configured so the created container can connect easily to the correct network and service.

For connection to the Docker daemon, additional environment variables are accepted; `DOCKER_HOST`, `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH`. They are same as those used by the Docker command-line client.

YAML schemas
------------

ArangoDB may be schemaless, but in a larger project it still makes sense to keep a schema spec up to date, both for an overview of collections and their data structures, and as a basis for validation.

migrado uses a schema model based on JSON Schema, in YAML, and can use this to generate an initial migration for the collections available in your database.

Example schema:

```yaml
---
all: &all
  _id:
    type: string
    readOnly: true
  _key:
    type: string
    readOnly: true
  _rev:
    type: string
    readOnly: true

edges: &edges
  _from:
    type: string
  _to:
    type: string

collections:

  books:
    type: object
    properties:
      <<: *all
      title:
        type: string
      isbn:
        type: string
    required:
      - title
      - isbn

  authors: 
    # Note, you do not actually need to specify the object schema,
    # but they can be used in API specs (e.g. OpenAPI) and/or validation,
    # and may be handled by migrado in the future.

edge_collections:

  # authors --> books 
  author_of:
    type: object
    properties:
      <<: *all
      <<: *edges
    required:
      - _from
      - _to
``` 

Migration scripts
-----------------

Migration scripts are structured so they may be parsed and run easily by both migrado and ArangoDB. In addition, they are structured so they may be run manually against ArangoDB using `arangosh`.

There are two types of script, **data** and **schema** migration scripts.

### Data migrations

You need to declare all collections subject to write operations using the syntax `// write collection_name`, because ArangoDB needs this information for locking during transactions. We've made the declaration explicit to reduce errors. _Attempting to write to collections not declared in this way will cause the migration to fail._

In general, a reverse migration should do the logical opposite of a forward migration. `forward()` and `reverse()` functions can contain anything that the ArangoDB V8 engine understands, but must be fully self-contained. _Anything outside these functions is ignored and unavailable when running migrations._

Here's an example migration script for adding `new_field` in collection `things`:

```javascript
// write things

function forward() {
    var db = require("@arangodb").db
    db._query(`
        FOR thing IN things
            UPDATE thing WITH { new_field: "some value" } IN things
    `)
}

function reverse() {
    var db = require("@arangodb").db
    db._query(`
        FOR thing IN things
            REPLACE thing WITH UNSET(thing, "new_field") IN things
    `)
}
```

Please make sure you read [limitations when running transactions](https://www.arangodb.com/docs/stable/transactions-limitations.html) in the ArangoDB documentation. In particular, _creation and deletion of databases, collections, and indexes_ is not allowed in transactions.

If a migration contains such operations, you will be asked if you want to run the migration through Docker.

### Schema migrations

Schema migrations are stuctured in the same way as data migrations, but are run against `arangosh` in a container from an [official arangodb Docker image](https://hub.docker.com/_/arangodb). There is no transaction safety when running schema migrations.

Schema migrations are structured the same way as data migrations, but `// write` declarations are not required. All operations are allowed.

Here's an example migration script generated from the YAML schema above:

```javascript
function forward() {
    var db = require("@arangodb").db
    db._createDocumentCollection("books")
    db._createDocumentCollection("authors")
    db._createEdgeCollection("author_of")
}

function reverse() {
    var db = require("@arangodb").db
    db._drop("books")
    db._drop("authors")
    db._drop("author_of")
}
```

Please be careful when running schema migrations in reverse. As you can see, the `reverse()` function above would drop your collections if you were to reverse beyond this point. Currently, you will not be able to do so for an initial migration.

TODO
----
- [ ] Authentication against Docker and ArangoDB
- [ ] Transaction-like safe runs for schema migrations
- [ ] Automatic diffing of schema migrations
- [ ] Using migrado to add indexes
- [ ] Using migrado to add recurring tasks

License
-------

migrado is copyright © 2019 Protojour AS, and is licensed under MIT. See [LICENSE.txt](./LICENSE.txt) for details.
