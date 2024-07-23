# https://github.com/casey/just
# https://just.systems/

dev:
    hivemind Procfile

dev-with-tunneling:
    ./bin/wait-for-pg.sh --help
    hivemind Procfile.tunneling

start: dev

pretty:
    ruff format peterbecom

lint: pretty
    ruff check peterbecom

format: pretty

install:
    pip install -r requirements.txt

test:
    pytest
