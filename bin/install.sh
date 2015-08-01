#!/bin/bash
# pwd is the git repo.
set -e

# Before installation, we'll run ``pip wheel``, this will build wheels for
# anything that doesn't already have one on PyPI.
pip wheel -r requirements.txt

echo "Install Python dependencies"
pip install -r requirements.txt

echo "Creating a test database"
psql -c 'create database peterbecom;' -U postgres
