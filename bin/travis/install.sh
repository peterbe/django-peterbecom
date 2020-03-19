#!/bin/bash
# pwd is the git repo.
set -e

echo "Install latestish pip"
pip install -U pip wheel

echo "Install Python dependencies"
pip install -r requirements.txt

echo "Install latest flake8"
# Perhaps this should be in some dev-requirements.txt but YOLO
pip install flake8

echo "Installing the node packages"
yarn

# Commented out as of Dec 2018 because the version of nodejs I get is too old.
# Switch to Xenial opened up other errors. Too lazy to fix this now.
echo "Install packages for adminui"
pushd adminui
yarn
popd
