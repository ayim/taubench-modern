# Publishing/Consuming Sema4.ai Agent Server Packages

We use a private AWS CodeArtifact repository to store and distribute our packages. This guide explains how to publish 
new versions of the Sema4.ai Agent Server packages as well as how to setup a project that uses them as dependencies.

## Prerequisites

* The `aws` CLI tool installed and available on your system path.
* `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are available as environment variables, and set to the values
   found [in this 1Password credential](https://start.1password.com/open/i?a=V76MNFP2PVEBDIXRX464NINPIU&v=4ivcsq3oqozclguoxecwulk3hy&i=h5saze2tqh6jpreu6fd4alfl5a&h=robocorp.1password.com).


## Versioning and Releasing
We use [Semantic Versioning](https://semver.org/) for versioning our packages. And use 
[bump-my-version](https://github.com/callowayproject/bump-my-version) to manage replacing version strings in files.

### Steps to Release/Publish a New Version
1. Based on semantic versioning decide whether this is a major, minor, or patch release.
2. Run `bump-my-version <major|minor|patch>`
   This will update version information, commit the changes, and create a new version tag.
3. Push the changes to the repository `git push origin main --tags`. This will trigger the GitHub Actions workflow to 
   publish the new version to the CodeArtifact repository.

## How to Install the Package
Projects that use the Sema4.ai Agent Server packages can install them using the following steps:

1. Add the following line to the `pyproject.toml` file:
```ini
[[tool.poetry.source]]
name = "pypi-public"
url = "https://pypi.org/simple/"

[[tool.poetry.source]]
name = "codeartifact"
url = "https://sema4ai-710450854638.d.codeartifact.eu-west-1.amazonaws.com/pypi/agent-server/simple/"
priority = "supplemental"
```

2. Run the following or `source` a file that does the same thing:
```shell
export CODEARTIFACT_TOKEN=$(aws codeartifact get-authorization-token --domain sema4ai --query authorizationToken --output text --region eu-west-1)
export POETRY_HTTP_BASIC_CODEARTIFACT_USERNAME=aws
export POETRY_HTTP_BASIC_CODEARTIFACT_PASSWORD=$CODEARTIFACT_TOKEN
```

3. Add the package to your project using the following command(s):
```shell
# let the poetry dependency resolver pick the version
poetry add sema4ai-agent-server

# specify a particular version
poetry add sema4ai-agent-server@0.1.0
```