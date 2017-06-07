#!/bin/bash

rm -fr ../peterbecom-static-content/songsearch-autocomplete
aunpack -X ../peterbecom-static-content/ songsearch-autocomplete.zip

./_insert.py
