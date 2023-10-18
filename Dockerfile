FROM python:3.12-slim-bookworm

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN apt-get -y update && \
    apt-get -y install curl
RUN curl -o /tmp/arango-client.deb https://download.arangodb.com/arangodb311/DEBIAN/amd64/arangodb3-client_3.11.4-1_amd64.deb \
    && dpkg -i /tmp/arango-client.deb \
    && rm /tmp/arango-client.deb
RUN apt-get -y autoremove curl

WORKDIR /app
RUN pip install migrado
COPY README.md LICENSE.txt /app/

USER ${USER_ID}:${GROUP_ID}

ENTRYPOINT ["migrado"]
