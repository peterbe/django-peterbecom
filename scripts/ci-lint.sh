#!/bin/bash

set -e

ruff peterbecom
black --check peterbecom
