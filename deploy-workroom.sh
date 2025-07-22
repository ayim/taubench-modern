#!/bin/bash

set -euo pipefail

REGION="europe-west1"
PROJECT_ID="$(gcloud config get-value project)"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/workroom:latest"
LOCAL_IMAGE="local-workroom-test"

echo "Tagging local image..."
docker tag "$LOCAL_IMAGE" "$IMAGE_NAME"

echo "Authenticating Docker with Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "Pushing image to Artifact Registry..."
docker push "$IMAGE_NAME"

echo "Deploying to Cloud Run..."
gcloud run deploy workroom \
  --image="$IMAGE_NAME" \
  --platform=managed \
  --region="$REGION" \
  --allow-unauthenticated \
  --ingress=all \
  --port=3001 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=300 \
  --cpu-boost \
  --execution-environment=gen2 \
  --set-env-vars="AGENT_SERVER_HOST=${AGENT_SERVER_HOST:-unset},AGENT_SERVER_PORT=443,DEPLOYMENT_TYPE=spar,META_URL=https://workroom-390062264543.europe-west1.run.app,NODE_ENV=production" \
  --quiet

echo "✅ Deployment complete."
