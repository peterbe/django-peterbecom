#!/bin/bash

INLINE_RUNTIME_CHUNK=false yarn run build

rm -fr build.zip
pushd build

# Clean things up first
find . | grep --color=never '\~$' |  xargs rm -f
find . -name '\.DS_Store' | xargs rm -fr

time zopfli -i500 static/js/*.js
time zopfli -i500 static/css/*.css
time brotli static/js/*.js
time brotli static/css/*.css
mv static songsearch-autocomplete
apack songsearch-autocomplete.zip songsearch-autocomplete
mv songsearch-autocomplete.zip ..
mv songsearch-autocomplete static
popd
aunpack -l songsearch-autocomplete.zip

scp build.zip django@192.34.57.223:/home/django/django-peterbecom/adminui/
