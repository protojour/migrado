FROM python:3.12-slim-bookworm

RUN apt-get -y update && \
    apt-get -y install curl make
RUN curl -o /tmp/arango-client.deb https://download.arangodb.com/arangodb311/DEBIAN/amd64/arangodb3-client_3.11.4-1_amd64.deb \
    && dpkg -i /tmp/arango-client.deb

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock LICENSE.txt README.md /app/
COPY migrado /app/migrado
RUN poetry install --no-interaction

CMD sleep 3 && \
    poetry run ruff check migrado && \
    poetry run pytest -svv --cov=migrado --cov-report term-missing; \
    make clean
