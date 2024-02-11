# https://github.com/casey/just
# https://just.systems/

dev:
    hivemind Procfile

pretty:
    black peterbecom

lint: pretty
    ruff peterbecom
    black --check peterbecom

format: pretty

install:
    pip install -r requirements.txt
