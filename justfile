# https://github.com/casey/just
# https://just.systems/

dev:
    hivemind Procfile

dev-with-tunneling:
    ./bin/wait-for-pg.sh --help > /dev/null
    hivemind Procfile.tunneling

start:
    hivemind Procfile.prod

pretty:
    ruff format peterbecom
    ruff check --fix peterbecom
    # correct import sort order
    ruff check --select I --fix

lint: pretty
    ruff check peterbecom

format: pretty

install:
    uv sync

test:
    ./bin/run.sh test

test-with-coverage:
    ./bin/run.sh test-with-coverage
    open htmlcov/index.html

upgrade:
    # uv pip list --outdated
    Uv-Outdated.py
