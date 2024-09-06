# Publishing/Consuming Sema4.ai Agent Server Packages

We use a private AWS CodeArtifact repository to store and distribute our packages. This guide explains how to publish 
new versions of the Sema4.ai Agent Server packages as well as how to setup a project that uses them as dependencies.

## Prerequisites

* The `aws` CLI tool installed and available on your system path.
* `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are available as environment variables, and set to the values
   found [in this 1Password credential](https://start.1password.com/open/i?a=V76MNFP2PVEBDIXRX464NINPIU&v=4ivcsq3oqozclguoxecwulk3hy&i=h5saze2tqh6jpreu6fd4alfl5a&h=robocorp.1password.com).


## Versioning and Releasing
We use [Semantic Versioning](https://semver.org/) for versioning our packages. And use 
[go-versionbump](https://github.com/ptgoetz/go-versionbump) to manage replacing version strings in files.

Install `go-versionbump` by running `go install github.com/ptgoetz/go-versionbump@latest`. This will install the
`versionbump` command on your system.

### Steps to Release/Publish a New Version
1. Based on semantic versioning decide whether this is a major, minor, or patch release.
2. Run `versionbump <major|minor|patch>`
   This will update version information, commit the changes, and create a new version tag.
3. Push the changes to the repository `git push origin main --tags`. This will trigger the GitHub Actions workflow to 
   publish the new version to github.
