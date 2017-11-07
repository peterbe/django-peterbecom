#!/bin/bash

FILEPATH="$(pwd)/.env"
DISTFILEPATH="$(pwd)/.env-dist"

if [ ! -f "${FILEPATH}" ]; then
    echo "# Copied $(git rev-parse --short HEAD | tr -d '\n') at $(date | tr -d '\n')" > "${FILEPATH}"
    echo "" >> "${FILEPATH}"
    cat < "${DISTFILEPATH}" >> "${FILEPATH}"
fi
