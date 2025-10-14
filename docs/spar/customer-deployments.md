# Team Edition Customer Deployments / Deliverables

Our Team Edition customer deliverables live in [sema4ai-external/sema4ai-team-edition-deployment](https://github.com/sema4ai-external/sema4ai-team-edition-deployment).

## GHCR Image Copy Script

This repository contains [a script](../infra//scripts/copy_spar_images_to_ghcr.sh) for copying the SPAR and Data Server images to the GitHub Container Registry (GHCR) under the `sema4ai-team-edition-deployment` repository. This is the mechanism for delivering the images to the customer when an AWS cross-account share directly from our ECR is not possible - for example when the customer is deploying to Azure.

The script will copy the images in following fashion:

- **From:** `024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/ace/spar`
  - **To:** `ghcr.io/sema4ai/s4te-spar`
- **From:** `024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/data/data-server`
  - **To:** `ghcr.io/sema4ai/s4te-data-server`

### Usage

Log in to both the source and destination registries first:

```bash
$ export AWS_PROFILE=sema4ai-releases-dev \
  && aws sso login \
  && aws ecr get-login-password --region us-east-1 \
    | docker login --username AWS --password-stdin 024848458368.dkr.ecr.us-east-1.amazonaws.com
$ docker login ghcr.io
Username: xxx [your GitHub username]
Password: xxx [a GitHub PAT under your user]
```

Then run the script:

```bash
# Adjust the source tags to copy, if necessary (defined within script)
$ vim ./infra/scripts/copy_spar_images_to_ghcr.sh
# Run the script
$ ./infra/scripts/copy_spar_images_to_ghcr.sh
```
