#!/bin/bash

set -e

# Set variables
NAMESPACE="ten-0c8a9114-fddc-4251-b546-13b99bd7dd9e"
SERVICE_NAME="agent-server"
PORT_TO_FORWARD=8000
ECR_REPO="024848458368.dkr.ecr.us-east-1.amazonaws.com/manual/ace/agent-server"
DEPLOYMENT_NAME="agents-backend"
POD_LABEL="app=backend"  # Correct label for the agents-backend deployment
# AWS region (replace with your region if different)
AWS_REGION="us-east-1"

# Ensure AWS_PROFILE is set
if [ -z "$AWS_PROFILE" ]; then
    echo "AWS_PROFILE is not set. Please set it to your desired AWS profile."
    exit 1
fi

# Get current image information from the deployment
CURRENT_IMAGE=$(kubectl get deployment $DEPLOYMENT_NAME -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "Current image: $CURRENT_IMAGE"

# Extract the current tag
CURRENT_TAG=$(echo $CURRENT_IMAGE | cut -d ':' -f 2)
echo "Current tag: $CURRENT_TAG"

# Check for running pods
PODS_COUNT=$(kubectl get pods -n $NAMESPACE -l $POD_LABEL --no-headers | wc -l)
if [ "$PODS_COUNT" -eq "0" ]; then
    echo "No running pods found for deployment $DEPLOYMENT_NAME. Exiting."
    exit 1
fi

# Get the node name where the pod is running
NODE_NAME=$(kubectl get pod -n $NAMESPACE -l $POD_LABEL -o jsonpath='{.items[0].spec.nodeName}')
if [ -z "$NODE_NAME" ]; then
    echo "No node information found for the pod. Exiting."
    exit 1
fi
echo "Node name: $NODE_NAME"

# Get the node architecture
NODE_ARCHITECTURE=$(kubectl get node $NODE_NAME -o jsonpath='{.status.nodeInfo.architecture}')
if [ -z "$NODE_ARCHITECTURE" ]; then
    echo "No architecture information found for the node. Exiting."
    exit 1
fi
echo "Node architecture: $NODE_ARCHITECTURE"

# Function to generate a new tag
generate_new_tag() {
    local username=$(whoami)
    local timestamp=$(date +"%Y%m%d%H%M")
    echo "${SERVICE_NAME}-${username}-${timestamp}-test"
}

# Generate a new tag
NEW_TAG=$(generate_new_tag)
echo "New tag: $NEW_TAG"

# Authenticate Docker to ECR using AWS_PROFILE
echo "Authenticating Docker to ECR using AWS profile: $AWS_PROFILE"
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | docker login --username AWS --password-stdin $ECR_REPO

# Function to build and push the new image
build_and_push_image() {
    local new_image="${ECR_REPO}:${NEW_TAG}"
    echo "Building new image for architecture: $NODE_ARCHITECTURE"
    docker buildx build --platform linux/$NODE_ARCHITECTURE -t $new_image \
        --build-arg TARGETOS=linux \
        --build-arg TARGETARCH=$NODE_ARCHITECTURE \
        --build-arg AGENT_SERVER_PORT=$PORT_TO_FORWARD \
        .
    echo "Pushing new image to ECR"
    docker push $new_image
}

# Function to update the deployment
update_deployment() {
    local new_image="${ECR_REPO}:${NEW_TAG}"
    echo "Updating deployment to use new image: $new_image"
    kubectl set image deployment/$DEPLOYMENT_NAME agent-server=$new_image -n $NAMESPACE
    echo "Waiting for rollout to complete..."
    kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE
}

# Function to port forward
setup_port_forward() {
    # Get the name of the new pod using the correct label
    NEW_POD_NAME=$(kubectl get pods -n $NAMESPACE -l $POD_LABEL -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$NEW_POD_NAME" ]; then
        echo "No pods found for port forwarding. Exiting."
        exit 1
    fi
    echo "Setting up port forwarding from pod $NEW_POD_NAME to localhost:$PORT_TO_FORWARD"
    kubectl port-forward $NEW_POD_NAME $PORT_TO_FORWARD:$PORT_TO_FORWARD -n $NAMESPACE
}

# Main execution
echo "Starting pod update process..."
build_and_push_image
update_deployment
setup_port_forward

echo "Process completed. You can now access the service at localhost:$PORT_TO_FORWARD"
