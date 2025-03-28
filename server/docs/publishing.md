# Publishing/Consuming Sema4.ai Agent Server Packages

We build and release wheels and executables for major platforms via GitHub Actions. Creating a tag with the format `v<major>.<minor>.<patch>` will trigger the release process.

## Versioning and Releasing

We use [Semantic Versioning](https://semver.org/) for versioning our packages. And use
[go-versionbump](https://github.com/ptgoetz/go-versionbump) to manage replacing version strings in files.

Install `go-versionbump` by running `go install github.com/ptgoetz/go-versionbump@latest`. This will install the `versionbump` command on your system.

### Steps to Release/Publish a New Version

1. Based on semantic versioning decide whether this is a major, minor, or patch release.
2. Run `versionbump <major|minor|patch|prerelease-<prerelease_type>>`. For example, if this is a patch release run `versionbump patch`. This will update version information, commit the changes, and create a new version tag.
3. Push the changes to the repository `git push origin --tags`. This will trigger the GitHub Actions workflow to publish the new version to github.
