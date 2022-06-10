FROM python:3.10-slim-bullseye

RUN apt-get -y update && \
    apt-get -y install wget make
RUN wget --progress=bar:force https://download.arangodb.com/arangodb39/Community/Linux/arangodb3-client_3.9.1-1_amd64.deb -O /tmp/arango_client.deb
RUN dpkg -i /tmp/arango_client.deb
RUN rm /tmp/arango_client.deb
RUN apt-get autoremove -y wget

WORKDIR /app
COPY pyproject.toml requirements.dev LICENSE.txt README.md /app/
COPY migrado /app/migrado
RUN pip install -r requirements.dev
RUN pip install .

CMD sleep 3 && \
    pylint -E migrado && \
    pytest -svv --cov=migrado --cov-report term-missing; \
    make clean
