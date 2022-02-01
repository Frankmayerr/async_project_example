FROM registry.tech.bank24.int/hr-it/python:latest

ENV POETRY_VIRTUALENVS_CREATE=0 PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install

COPY . .

RUN chmod +x ./*.sh

ENTRYPOINT [ "/app/entrypoint.sh" ]

CMD [ "python", "app/main.py" ]
