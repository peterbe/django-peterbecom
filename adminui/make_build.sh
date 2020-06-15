#!/bin/bash

INLINE_RUNTIME_CHUNK=false yarn run build

rm -fr build.zip
pushd build
time zopfli -i500 static/js/*.js
time zopfli -i500 static/css/*.css
time brotli static/js/*.js
time brotli static/css/*.css
popd
apack build.zip build


scp build.zip django@68.183.151.74:/home/django/django-peterbecom/adminui/
