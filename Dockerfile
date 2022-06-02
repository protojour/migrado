FROM python:3.10

RUN apt-get -y update && \
    apt-get -y install apt-transport-https
RUN curl -OL https://download.arangodb.com/arangodb39/DEBIAN/Release.key
RUN apt-key add Release.key >/dev/null
RUN echo 'deb https://download.arangodb.com/arangodb39/DEBIAN/ /' > /etc/apt/sources.list.d/arangodb.list
RUN apt-get -y update && \
    apt-get -y install arangodb3-client

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml /app
RUN poetry install --no-interaction

COPY . /app

CMD sleep 3 && \
    poetry run pylint -E migrado && \
    poetry run pytest -svv --cov=migrado --cov-report term-missing; \
    make clean
