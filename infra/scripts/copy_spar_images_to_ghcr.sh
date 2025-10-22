#!/usr/bin/env bash

set -euo pipefail

##############################################################################
# This script copies the spar and data-server images to the GitHub Container #
# Registry and links them to the Team Edition external repository at         #
# https://github.com/sema4ai-external/sema4ai-team-edition-deployment        #
# making them available for customers that have been granted access to the   #
# repository.                                                                #
#                                                                            #
# NOTE: Running the script requires logging in to the following registries:  #
# - 024848458368.dkr.ecr.us-east-1.amazonaws.com (releases-dev)              #
# - ghcr.io (docker login ghcr.io with username + PAT as password)           #
##############################################################################

# Tag + repos for `spar` image
spar_tag="2.1.12_bffd7477.20251021T075351Z"
spar_ecr_repository="024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/ace/spar"
spar_ghcr_repository="ghcr.io/sema4ai-external/s4te-spar"

# Tag + repos for `data-server` image
data_server_tag="1.1.15_e65fbf8.20250916T124606Z"
data_server_ecr_repository="024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/data/data-server"
data_server_ghcr_repository="ghcr.io/sema4ai-external/s4te-data-server"

# The GitHub repository the images should be linked to (available from repo sidebar under "packages")
linked_github_repository_url="https://github.com/sema4ai-external/sema4ai-team-edition-deployment"

if ! command -v crane &> /dev/null; then
  echo "Error: crane is not installed" >&2
  echo "See instructions in https://github.com/google/go-containerregistry/blob/main/cmd/crane/README.md" >&2
  exit 1
fi

spar_src="${spar_ecr_repository}:${spar_tag}"
spar_dst="${spar_ghcr_repository}:${spar_tag}"
crane copy "${spar_src}" "${spar_dst}"
crane mutate \
  --label "org.opencontainers.image.source=${linked_github_repository_url}" \
  "${spar_dst}"

data_server_src="${data_server_ecr_repository}:${data_server_tag}"
data_server_dst="${data_server_ghcr_repository}:${data_server_tag}"
crane copy "${data_server_src}" "${data_server_dst}"
crane mutate \
  --label "org.opencontainers.image.source=${linked_github_repository_url}" \
  "${data_server_dst}"

echo "##############################################################################"
echo "Images copied successfully:"
echo "- ${spar_dst}"
echo "- ${data_server_dst}"
