# Agent Platform Development Guide

## Developer Workflow

### Branching Strategy

- **Default Branch**: `development`
- **Protected Branch**: `main`
- **Release Branch**: `release` or branches starting with `release-`

### Merge Rules

- **Squash Merge**: Allowed only for merging feature branches into `development`.
- **Merge Commit**: Required for merging `development` into `main` or `release` branches.

### Workflow Overview

1. **Feature Development**:

   - Create a feature branch from `development`.
   - Implement your changes.
   - Create a change fragment to document your work (see [Change Management](#change-management)).
   - Run `make check-pr` to ensure your changes pass all checks.
   - Open a Pull Request (PR) to merge your feature branch into `development` using a squash merge.
   - Optioanlly, you may build a feature-branch pre-release, see [Feature Branch Builds](#feature-branch-builds).

2. **Pre-Release**:

   - Once your feature branch is merged into `development`, trigger the `Prerelease Agent Server` workflow on the `development` branch.
   - When triggering the workflow, select an appropriate version bump strategy (see [Version Bump Strategy](#version-bump-strategy)).
   - This workflow will:
     - Bump the version as a pre-release.
     - Build and sign executables for all platforms.
     - Parse all new change fragments and write them to the pre-release changelog.
     - Publish the pre-release to GitHub Releases and deploy to the CDN.

3. **Release**:
   - When ready for a new version, open a PR to merge `development` into `main` or a `release` branch using a merge commit.
   - Once the PR is merged, trigger the `Release Agent Server` workflow.
   - This workflow will:
     - Bump the version as a release.
     - Build and sign executables for all platforms.
     - Parses all prereleased change fragments and writes them to the release changelog, also clears out the pre-release changelog.
     - Publish the release to GitHub Releases and deploy to the CDN.
   - A separate workflow will automatically create a merge commit from `main` back to `development` to keep the branches in sync.

## Change Management

Every code change that affects functionality should include a change fragment to document the change in the changelog. Use the following command to create a change fragment:

```bash
make change
```

This will interactively prompt you for:

1. The type of change (feature, bugfix, doc, removal, misc)

   - You may use the `hidden` type to mark changes that should not be included in the changelog; however, if you do not include a valid linear ticket number, the change _will_ be included in the changelog.

2. The Linear issue ID (e.g., GPT-123)
3. The section (Core server changes, Public API, Private API)
4. A brief description of the change

Change fragments are stored in the `changes/new` directory and will be automatically included in the next pre-release and release.

> **Note**: Feature branch builds will not build changes.

## Version Bump Strategy

When triggering the prerelease workflow, you must select an appropriate version bump strategy:

### For Non-Main/Release Branches

- **New Pre-Release**:
  - `new-pre-major`: Start a new major version pre-release (e.g., `1.0.0` → `2.0.0-alpha`).
  - `new-pre-minor`: Start a new minor version pre-release (e.g., `1.0.0` → `1.1.0-alpha`).
  - `new-pre-patch`: Start a new patch version pre-release (e.g., `1.0.0` → `1.0.1-alpha`).
- **Existing Pre-Release**:
  - `pre`: Bump the pre-release label (e.g., `1.0.0-alpha` → `1.0.0-beta`).
  - `pre-major`: Bump the major component of the pre-release subversion (e.g., `1.0.0-alpha` → `1.0.0-alpha.1`).
  - `pre-build`: Bump or add a build component to the pre-release version (e.g., `1.0.0-alpha` → `1.0.0-alpha+1`).

### For Main/Release Branches

- Only the `release` bump type is allowed on `main`, `release`, or `release-*` branches.

You can view all available version bump strategies by installing [versionbump](https://github.com/ptgoetz/go-versionbump) and running:

```bash
versionbump show
```

## Local Development

### Environment Setup

1. Set up your development environment:

```bash
# Install all dependencies
make sync
```

2. For local testing, you may want to set up environment variables:

```bash
# Create a new empty .env file with required variables (you'll need to fill these in)
make new-empty-env
```

### Common Development Tasks

```bash
# Run unit tests
make test-unit

# Run integration tests (requires environment variables)
make test-integration

# Run linting
make lint

# Fix linting issues
make lint-fix

# Run typechecking
make typecheck

# Format code
make format

# Build the agent server executable
make build-exe

# Run the agent server from Python
make run-server

# Run the agent server executable
make run-server-exe

# Create a new change fragment
make change

# Run all PR checks (format, lint, typecheck, unit tests, change check)
make check-pr
```

## Feature Branch Builds

Sometimes you may need to create a special build from a feature branch before merging to development. This is useful for testing or sharing builds with specific features:

1. Create your feature branch from `development` and implement your changes.
2. Modify the build label in the `versionbump.yaml` file of the project you're working on:

   ```yaml
   # Find the build-label line in the versionbump.yaml file
   build-label: 'dev'
   # Change it to include your linear ticket id or feature name
   build-label: 'gpt123'
   ```

3. Trigger the `Prerelease Agent Server` workflow on your feature branch.
4. Select the `pre-build` bump type when running the workflow.
5. This will create a special build with your feature name in the version.

This approach allows you to distribute feature-specific builds for testing while maintaining proper version tracking.

## CI/CD Pipelines

The project uses GitHub Actions for CI/CD. The main workflows are:

1. **Test Agent Server**: Runs on every PR and push to main/development branches.

   - Includes linting, typechecking, formatting checks, and unit tests.

2. **Prerelease Agent Server**: Manually triggered workflow for creating prereleases.

   - Must be run on a non-main, non-release branch (typically `development`).
   - Bumps version, builds and signs executables, and deploys to GitHub Releases and CDN.

3. **Release Agent Server**: Manually triggered workflow for creating releases.
   - Must be run on `main`, `release`, or a `release-*` branch.
   - Bumps version, builds and signs executables, and deploys to GitHub Releases and CDN.

## Executable Builds and Distribution

Executables are built for:

- Windows x64
- macOS x64
- macOS ARM64
- Linux x64

The build process uses PyInstaller with a Go wrapper to create standalone executables.
Executables are signed and notarized (on macOS) before distribution.

Releases are published to:

1. GitHub Releases
2. Content Delivery Network (CDN) for direct downloads
