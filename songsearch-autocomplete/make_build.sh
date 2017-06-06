#!/bin/bash

yarn run build

rm -fr build.zip
pushd build
mv static songsearch-autocomplete
apack songsearch-autocomplete.zip songsearch-autocomplete
mv songsearch-autocomplete.zip ..
mv songsearch-autocomplete static
popd
aunpack -l songsearch-autocomplete.zip
