FROM python:3.7

WORKDIR /app
RUN pip install poetry
COPY pyproject.toml /app
RUN poetry install --no-interaction

COPY . /app

CMD sleep 3 && \
    poetry run pylint -E migrado && \
    poetry run pytest -svv --cov=migrado; \
    make clean
