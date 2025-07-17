#!/bin/bash

set -e

[[ -z "${META_URL}" ]] && { echo "Must specify META_URL" ; exit 1; }

if [[ "$DEPLOYMENT_TYPE" == "ace" ]]; then
  cp /etc/nginx/nginx.ace.conf /etc/nginx/nginx.conf
elif [[ "$DEPLOYMENT_TYPE" == "spar" ]]; then
  cp /etc/nginx/nginx.spar.conf /etc/nginx/nginx.conf
else
  echo "Invalid deployment type or not specified: ${DEPLOYMENT_TYPE}"
  exit 1
fi

sed -i "s,:META_URL,${META_URL}," /etc/nginx/nginx.conf

nginx
