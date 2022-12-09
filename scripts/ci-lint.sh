#!/bin/bash

set -e

flake8 peterbecom
black --check peterbecom
