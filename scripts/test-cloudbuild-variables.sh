#!/bin/bash

# Test script to debug Cloud Build variables and Docker setup
# This script simulates what happens in Cloud Build to help debug issues

set -e

echo "🔍 Testing Cloud Build Variable Access..."
echo ""

# Test variables that should be available
echo "📊 Environment Variables:"
echo "BUILD_ID: '${BUILD_ID:-NOT_SET}'"
echo "PROJECT_ID: '${PROJECT_ID:-NOT_SET}'"
echo "_PROJECT_ID: '${_PROJECT_ID:-NOT_SET}'"
echo "REGION: '${REGION:-NOT_SET}'"
echo "_REGION: '${_REGION:-NOT_SET}'"
echo ""

# Test gcloud authentication
echo "🔐 Testing gcloud authentication..."
if gcloud auth list --quiet; then
  echo "✅ gcloud authenticated"
  CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" --quiet)
  echo "👤 Current user: $CURRENT_USER"
else
  echo "❌ gcloud not authenticated"
  exit 1
fi
echo ""

# Use defaults if not set
PROJECT_ID=${_PROJECT_ID:-"sema4-portable-agent-runtime"}
REGION=${_REGION:-"europe-west1"}
BUILD_ID=${BUILD_ID:-"test-$(date +%Y%m%d-%H%M%S)"}

echo "📊 Using values:"
echo "PROJECT_ID: $PROJECT_ID"
echo "REGION: $REGION"
echo "BUILD_ID: $BUILD_ID"
echo ""

# Test project access
echo "🏗️ Testing project access..."
if gcloud projects describe "$PROJECT_ID" --quiet >/dev/null 2>&1; then
  echo "✅ Can access project $PROJECT_ID"
else
  echo "❌ Cannot access project $PROJECT_ID"
  exit 1
fi
echo ""

# Test Artifact Registry
echo "🏗️ Testing Artifact Registry..."
REGISTRY_URL="${REGION}-docker.pkg.dev"
REPO_URL="${REGISTRY_URL}/${PROJECT_ID}/cloud-run-source-deploy"

if gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" --quiet >/dev/null 2>&1; then
  echo "✅ Artifact Registry repository exists"
else
  echo "❌ Artifact Registry repository doesn't exist"
  echo "   You can create it with:"
  echo "   gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location=$REGION"
  # Don't exit here since the build script will create it
fi
echo ""

# Test Docker authentication
echo "🐳 Testing Docker authentication..."
echo "Configuring Docker for $REGISTRY_URL..."
if gcloud auth configure-docker "$REGISTRY_URL" --quiet; then
  echo "✅ Docker authentication configured"
else
  echo "❌ Failed to configure Docker authentication"
  exit 1
fi

# Test Docker access to registry
echo "Testing Docker registry access..."
TEST_IMAGE="hello-world:latest"
TAGGED_IMAGE="${REPO_URL}/test:${BUILD_ID}"

echo "Pulling hello-world image..."
if docker pull "$TEST_IMAGE"; then
  echo "✅ Docker pull works"
else
  echo "❌ Docker pull failed"
  exit 1
fi

echo "Tagging image as: $TAGGED_IMAGE"
if docker tag "$TEST_IMAGE" "$TAGGED_IMAGE"; then
  echo "✅ Docker tag works"
else
  echo "❌ Docker tag failed"
  exit 1
fi

echo "Testing push to registry..."
if docker push "$TAGGED_IMAGE"; then
  echo "✅ Docker push works"
  echo "🧹 Cleaning up test image..."
  gcloud artifacts docker images delete "$TAGGED_IMAGE" --quiet --delete-tags 2>/dev/null || true
else
  echo "❌ Docker push failed"
  echo "This suggests a permissions issue with Artifact Registry"
  exit 1
fi

echo ""
echo "✅ All tests passed! Cloud Build should work correctly."
echo ""
echo "🚀 Ready to run:"
echo "   gcloud builds submit --config=cloudbuild.yaml ." 