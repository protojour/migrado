FROM python:3.12-bookworm

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN curl -o /tmp/arango-client.deb https://download.arangodb.com/arangodb311/DEBIAN/amd64/arangodb3-client_3.11.4-1_amd64.deb \
    && dpkg -i /tmp/arango-client.deb \
    && rm /tmp/arango-client.deb

WORKDIR /app
RUN pip install migrado

USER ${USER_ID}:${GROUP_ID}
COPY README.md .
COPY LICENSE.txt .

ENTRYPOINT [ "migrado" ]
