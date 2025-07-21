#!/bin/bash

set -e

if [[ "$DEPLOYMENT_TYPE" == "ace" ]]; then
  cp /etc/nginx/nginx.ace.conf /etc/nginx/nginx.conf
elif [[ "$DEPLOYMENT_TYPE" == "spar" ]]; then
  cp /etc/nginx/nginx.spar.conf /etc/nginx/nginx.conf
else
  echo "Invalid deployment type or not specified: ${DEPLOYMENT_TYPE}"
  exit 1
fi

[[ -z "${META_URL}" ]] && { echo "Must specify META_URL" ; exit 1; }
[[ -z "${AGENT_SERVER_URL}" ]] && { echo "Must specify AGENT_SERVER_URL" ; exit 1; }
[[ -z "${WORKROOM_URL}" ]] && { echo "Must specify WORKROOM_URL" ; exit 1; }

sed -i "s,:META_URL,${META_URL}," /etc/nginx/nginx.conf
sed -i "s,:AGENT_SERVER_URL,${AGENT_SERVER_URL}," /etc/nginx/nginx.conf
sed -i "s,:WORKROOM_URL,${WORKROOM_URL}," /etc/nginx/nginx.conf

exec nginx
