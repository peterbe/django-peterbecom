# https://github.com/casey/just
# https://just.systems/

dev:
    hivemind Procfile

elasticsearch:
    hivemind -l elasticsearch Procfile
    echo "Now you can run `just test`"

dev-with-tunneling:
    ./bin/wait-for-pg.sh --help > /dev/null
    hivemind Procfile.tunneling

start: dev

pretty:
    ruff format peterbecom
    ruff check --fix peterbecom

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
    /Users/peterbe/bin/Uv-Outdated.py
