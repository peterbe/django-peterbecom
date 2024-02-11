# https://github.com/casey/just
# https://just.systems/

dev:
    hivemind Procfile

start: dev

pretty:
    ruff format peterbecom

lint: pretty
    ruff check peterbecom

format: pretty

install:
    pip install -r requirements.txt
