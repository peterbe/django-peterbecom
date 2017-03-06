#!/bin/bash
# pwd is the git repo.
set -e

echo "Install latestish pip"
pip install "pip==8.1.2"

# Before installation, we'll run ``pip wheel``, this will build wheels for
# anything that doesn't already have one on PyPI.
pip wheel -r requirements.txt

echo "Install Python dependencies"
pip install -r requirements.txt
