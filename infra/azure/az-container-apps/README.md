# Sema4.ai Team Edition - Azure Container Apps Deployment

## Deploying the Application

### 1. Authenticate with Azure CLI

Running Terraform requires authenticating with the Azure CLI (`az`).

```bash
az login
```

### 2. Configure Terraform State Storage

Terraform requires an Azure Storage Account Container to store infrastructure state.

Create a new container or identify an existing one, then update the **`PLACEHOLDER`** values in [backend-config-dev](./backend-config-dev) with your container details.

### 3. Initialize and Apply Terraform

Initialize the Terraform workspace:

```bash
terraform init -backend-config backend-config-dev
```

Provision the infrastructure:

```bash
terraform apply
```

:warning: Note the **output values**, as you'll need them when deploying the application.

### 4. Replace placeholders in OIDC configuration

The following Key Vault secrets are provisioned with placeholders that must be replaced with their proper values before launching the application:

- `oidc-client-id` - OIDC Client ID
- `oidc-client-secret` - OIDC Client Secret
- `oidc-server` - The discovery URL of your OIDC prodiver
  - For example `https://accounts.google.com/.well-known/openid-configuration`

### 5. Copy the container images from GitHub to your Azure Container Registry

First, **pull** the `s4te-spar` and `s4te-data-server` images to your local machine.

The latest tags for these images can be found in the sidebar of this repository, under "Packages".

```bash
docker pull ghcr.io/sema4ai-external/s4te-spar:0.0.0_12341234.20250101t000000z
docker pull ghcr.io/sema4ai-external/s4te-data-server:0.0.0_12341234.20250101t000000z
docker pull ghcr.io/sema4ai-external/s4te-mcp-runtime:0.0.0_12341234.20250101t000000z
```

Then, re-tag and **push** the images to your Azure Container Registry.

```bash
# We reference the Terraform outputs
ACR_LOGIN_SERVER="..." # Terraform: acr_login_server
ACR_REGISTRY_NAME="..." # Terraform: acr_registry_name

# Log in to the ACR registry
az acr login --name "${ACR_REGISTRY_NAME}"

# Copy the "SPAR" component image to ACR, exporting the reference for the deploy script (Step 6.)
export SPAR_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-spar:0.0.0_12341234.20250101t000000z"
docker tag \
  "ghcr.io/sema4ai-external/s4te-spar:0.0.0_12341234.20250101t000000z" \
  "${SPAR_IMAGE_REF}"
docker push "${SPAR_IMAGE_REF}"

# Copy the "Data Server" component image to ACR, exporting the reference for the deploy script (Step 6.)
export DATA_SERVER_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-data-server:0.0.0_12341234.20250101t000000z"
docker tag \
  "ghcr.io/sema4ai-external/s4te-data-server:0.0.0_12341234.20250101t000000z" \
  "${DATA_SERVER_IMAGE_REF}"
docker push "${DATA_SERVER_IMAGE_REF}"

# Copy the "MCP Runtime" component image to ACR, exporting the reference for the deploy script (Step 6.)
export MCP_RUNTIME_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-mcp-runtime:0.0.0_12341234.20250101t000000z"
docker tag \
  "ghcr.io/sema4ai-external/s4te-mcp-runtime:0.0.0_12341234.20250101t000000z" \
  "${MCP_RUNTIME_IMAGE_REF}"
docker push "${MCP_RUNTIME_IMAGE_REF}"
```

### 6. Deploy the Application by running the `deploy.sh` script:

Export the Terraform output values and run the deployment script:

```bash
export APP_ENVIRONMENT_ID="..." # Terraform: app_environment_id
export APP_UAI_ID="..." # Terraform: app_uai_id
export KEY_VAULT_URI="..." # Terraform: key_vault_uri
export RESOURCE_GROUP_NAME="..." # Terraform: resource_group_name
export ACR_LOGIN_SERVER="..." # Terraform: acr_login_server
# export DB_NAME="..." # Optional: Name used for the application database
# export RELEASE_NAME="..." # Optional: Name used for the Container App

./app-configuration/deploy.sh
```
