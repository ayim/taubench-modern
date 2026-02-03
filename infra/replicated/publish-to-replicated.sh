#!/usr/bin/env bash
#
# Publish SPAR to Replicated
#
# This script updates the Replicated manifests with the provided version and tag,
# packages the Helm chart, and creates a Replicated release.
#
# Required environment variables:
#   VERSION - The SPAR version (e.g., 2.2.18)
#   TAG     - The Docker image tag (e.g., 2.2.18_f2d79ce6c.20260129T223946Z)
#   REPLICATED_API_TOKEN - API token for Replicated CLI authentication
#
# Usage:
#   export VERSION="2.2.18"
#   export TAG="2.2.18_abc123.20260101T000000Z"
#   export REPLICATED_API_TOKEN="..."
#   ./infra/replicated/publish-to-replicated.sh

set -euo pipefail

# Validate required environment variables
: "${VERSION:?VERSION environment variable is required}"
: "${TAG:?TAG environment variable is required}"
: "${REPLICATED_API_TOKEN:?REPLICATED_API_TOKEN environment variable is required}"

export REPLICATED_APP=spar

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
replicated_dir="${repo_root}/infra/replicated"

echo "==> Installing Replicated CLI"
curl -s https://api.github.com/repos/replicatedhq/replicated/releases/latest \
  | grep "browser_download_url.*linux_amd64.tar.gz" \
  | cut -d : -f 2,3 \
  | tr -d \" \
  | wget -qi -
tar -xzf replicated_*_linux_amd64.tar.gz replicated
sudo mv replicated /usr/local/bin/
rm -f replicated_*_linux_amd64.tar.gz

echo "==> Updating Replicated manifests with version=${VERSION} tag=${TAG}"

# Update Chart.yaml version and appVersion
sed -i "s/^version: .*/version: '${VERSION}'/" "${replicated_dir}/Chart.yaml"
sed -i "s/^appVersion: .*/appVersion: '${VERSION}'/" "${replicated_dir}/Chart.yaml"

# Update manifests/spar.yaml chartVersion and tag
sed -i "s/chartVersion: .*/chartVersion: ${VERSION}/" "${replicated_dir}/manifests/spar.yaml"
sed -i "s/tag: .*/tag: ${TAG}/" "${replicated_dir}/manifests/spar.yaml"

echo "Updated Chart.yaml:"
cat "${replicated_dir}/Chart.yaml"

echo "==> Updating Helm dependencies"
helm dependency update "${replicated_dir}"

echo "==> Packaging Helm chart"
# Remove old tgz file
rm -f "${replicated_dir}/manifests/spar-"*.tgz

# Package the chart into the manifests directory
helm package "${replicated_dir}" -d "${replicated_dir}/manifests"

echo "Packaged Helm chart:"
ls -la "${replicated_dir}/manifests/"

echo "==> Creating Replicated release and promoting to Stable channel"
replicated release create --yaml-dir "${replicated_dir}/manifests" --promote Stable

echo "==> Done!"
