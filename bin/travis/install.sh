#!/bin/bash
# pwd is the git repo.
set -e

echo "Install latestish pip"
pip install -U pip wheel

echo "Install Python dependencies"
pip install -r requirements.txt

echo "Installing the node packages"
echo "But first, which version of yarn?"
yarn --version
yarn
