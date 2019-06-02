#!/bin/bash

set -ex

wget https://geolite.maxmind.com/download/geoip/database/GeoLite2-City.tar.gz

rm -fr /tmp/GeoLite2-City*
aunpack --extract-to=/tmp GeoLite2-City.tar.gz
mv /tmp/GeoLite2-City_*/*.mmdb .
rm GeoLite2-City.tar.gz

ls -lh *.mmdb
