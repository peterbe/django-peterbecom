#!/bin/bash
# pwd is the git repo.
set -e

echo "Install latestish pip"
pip install -U pip wheel

echo "Install Python dependencies"
pip install -r requirements.txt
