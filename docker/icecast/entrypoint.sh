#!/bin/sh
set -e

sed \
  -e "s/__SOURCE_PASSWORD__/${ICECAST_SOURCE_PASSWORD:-hackme}/g" \
  -e "s/__ADMIN_PASSWORD__/${ICECAST_ADMIN_PASSWORD:-hackme}/g" \
  /etc/icecast2/icecast.xml.template > /tmp/icecast.xml

exec icecast -c /tmp/icecast.xml
