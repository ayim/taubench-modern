#!/bin/bash

# Function to configure Poetry for a given repository
configure_poetry_for_repo() {
  local repo_url=$1
  local repo_name=$(echo $repo_url | sed -E 's|https://github.com/([^/]+)/([^/]+).git|\1/\2|')
  
  poetry config repositories.$repo_name $repo_url
  poetry config http-basic.$repo_name $GIT_USERNAME $GIT_TOKEN
}

# Read the pyproject.toml file and find all dependencies with a git source
grep -E 'git = "https://github.com/' pyproject.toml | while read -r line; do
  repo_url=$(echo $line | sed -E 's/.*git = "(https:\/\/github.com\/[^"]+)".*/\1/')
  configure_poetry_for_repo $repo_url
done