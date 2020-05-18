#!/bin/bash

set -e

# Make sure we're running Elasticsearch
curl -v http://localhost:9200/

pytest peterbecom
