FROM python:3.10-slim-bullseye

RUN apt-get -y update && \
    apt-get -y install wget make
RUN wget --progress=bar:force https://download.arangodb.com/arangodb39/Community/Linux/arangodb3-client_3.9.1-1_amd64.deb -O /tmp/arango_client.deb
RUN dpkg -i /tmp/arango_client.deb
RUN rm /tmp/arango_client.deb
RUN apt-get autoremove -y wget

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock LICENSE.txt README.md migrado /app/
RUN poetry install --no-interaction

CMD sleep 3 && \
    poetry run pylint -E migrado && \
    poetry run pytest -svv --cov=migrado --cov-report term-missing; \
    make clean
