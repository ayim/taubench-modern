#!/bin/bash

set -eou pipefail

terraform init -backend-config=backend-config-dev -reconfigure -upgrade

terraform apply -var-file=dev.tfvars
