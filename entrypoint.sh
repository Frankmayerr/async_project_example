#!/usr/bin/env bash

set -e

if [[ -d /var/run/secrets/app ]]; then
  . load-env /var/run/secrets/app
fi

exec "$@"
