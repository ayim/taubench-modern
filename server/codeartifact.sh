echo "Setting up CodeArtifact environment variables"
export CODEARTIFACT_TOKEN=$(aws codeartifact get-authorization-token --domain sema4ai --query authorizationToken --output text --region eu-west-1)
export POETRY_HTTP_BASIC_CODEARTIFACT_USERNAME=aws
export POETRY_HTTP_BASIC_CODEARTIFACT_PASSWORD=$CODEARTIFACT_TOKEN
