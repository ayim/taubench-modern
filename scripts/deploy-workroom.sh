#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

set -euo pipefail

REGION="europe-west1"
HOME="/Users/eventyret"
PROJECT_ID="$(gcloud config get-value project)"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/workroom:latest"
LOCAL_IMAGE="local-workroom-test"

echo "Tagging local image..."
 docker build \
          --platform linux/amd64 \
          --secret id=npmrc,src=${HOME}/.npmrc \
          --build-arg VITE_INSTANCE_ID=dev \
          --build-arg VITE_DEPLOYMENT_TYPE=spar \
          --build-arg VITE_DEV_WORKROOM_TENANT_LIST_URL=/spar-tenants-list \
          --build-arg VITE_DEV_SERVER_PORT=8001 \
          --build-arg NODE_ENV=production \
          --label "source-hash=MANUAL_BUILD" \
          --label "build-id=MANUAL_BUILD" \
          -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/workroom:latest \
          -f workroom/Dockerfile ./workroom

echo "Authenticating Docker with Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "Pushing image to Artifact Registry..."
#docker push "$IMAGE_NAME"
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/workroom:latest
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
  --set-env-vars="AGENT_SERVER_URL=https://agent-server-390062264543.europe-west1.run.app,DEPLOYMENT_TYPE=spar,META_URL=https://workroom-390062264543.europe-west1.run.app,WORKROOM_URL=https://workroom-390062264543.europe-west1.run.app,NODE_ENV=production" \
  --quiet

echo "✅ Deployment complete."
