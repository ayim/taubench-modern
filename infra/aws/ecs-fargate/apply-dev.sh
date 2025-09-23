#!/bin/bash

set -eou pipefail

terraform init -backend-config=backend-config-dev

terraform apply
