# Agent Platform Development Guide

## Developer Workflow

### Branching Strategy

- **Single Branch**: `main` (trunk-based development)
- **Protected Branch**: `main`

### Branch Protection Rules

- **Required Approvals**: 1 approver required for all PRs into `main`
- **No Built-in Bypass List**: Repository administrators can temporarily disable rule enforcement or add themselves to the bypass list when necessary
- **Breakglass Access**: Any admin bypass must be:
  - Logged in GitHub (automatic)
  - Documented with justification
  - Approved before use (or after if the issue is emergent enough to require immediate action)

### Merge Rules

- **Squash Merge**: Required for all merges into `main`

### Workflow Overview

1. **Feature Development**:

   - Create a feature branch from `main`.
   - Implement your changes.
   - Add your changes to the "Unreleased" section of the changelog (see [Change Management](#change-management)).
   - Run `make check-pr` to ensure your changes pass all checks.
   - Open a Pull Request (PR) to merge your feature branch into `main` using a squash merge.
   - **Automatic Build**: The PR will automatically trigger a build, test, and deployment to CDN with PR-specific versioning, plus Slack notification.

2. **Release Process**:

   - Once features are merged into `main`, update the version in `server/pyproject.toml` following [Semantic Versioning](#semantic-versioning).
   - Format the changelog: move items from "Unreleased" to a new release section (e.g., "# Agent Server 2.1.0").
   - Merge the version bump and changelog update into `main` using a squash merge.
   - Create and push a git tag matching the pattern `agent-server-v*` (e.g., `agent-server-v2.1.0`) on the `main` branch.
   - **Automatic Release**: The tag push will automatically:
     - Build and sign executables for all platforms.
     - Deploy to GitHub Releases and CDN.

3. **Pre-Release Process** (Optional):
   - For pre-release versions (alpha, beta, rc), follow the same process but use pre-release version numbers (e.g., `agent-server-v2.1.0-alpha.1`).
   - Pre-releases can be created directly from `main` when testing is needed before a final release.

### Tips

- **Verify version consistency**: The tag version must match `server/pyproject.toml`
- **Test PR builds**: Use the automatically generated PR builds for testing before releasing
- **Monitor Slack**: All builds send notifications with download links
- **Check CDN**: Downloads are available at `https://cdn.sema4.ai/agent-server/v{VERSION}/{platform}/agent-server`

## Change Management

Every code change that affects functionality should be documented in the changelog. Add your changes directly to the "Unreleased" section at the top of `server/CHANGELOG.md`.

### Changelog Format

Use the following format for changelog entries:

```markdown
# Unreleased

## Agent Server

### Features

- Your new feature description ([GPT-123](https://linear.app/sema4ai/issue/GPT-123))

### Bugfixes

- Your bug fix description ([GPT-456](https://linear.app/sema4ai/issue/GPT-456))

### Miscellaneous

- Other changes ([GPT-789](https://linear.app/sema4ai/issue/GPT-789))

## Public API

### Features

- API changes that affect public users

## Private API

### Features

- API changes that affect internal/private users
```

### Guidelines

- Always include the Linear ticket ID with a link: `([GPT-123](https://linear.app/sema4ai/issue/GPT-123))`
- Choose the appropriate section: Agent Server, Public API, or Private API
- Use clear, user-focused descriptions
- Group related changes under the appropriate category (Features, Bugfixes, Miscellaneous, etc.)

## Semantic Versioning

This project follows [Semantic Versioning (semver)](https://semver.org/) principles. Version numbers follow the format `MAJOR.MINOR.PATCH`, with optional pre-release identifiers.

### Version Format

- **MAJOR**: Incremented for incompatible API changes
- **MINOR**: Incremented for backwards-compatible functionality additions
- **PATCH**: Incremented for backwards-compatible bug fixes
- **Pre-release**: Optional suffix like `-alpha.1`, `-beta.2`, `-rc.1`

### Examples

- `2.0.0` → `2.0.1` (patch release for bug fixes)
- `2.0.0` → `2.1.0` (minor release for new features)
- `2.0.0` → `3.0.0` (major release for breaking changes)
- `2.1.0-alpha.1` (pre-release)
- `2.1.0-beta.1` → `2.1.0-beta.2` (iterating pre-releases)
- `2.1.0-rc.1` → `2.1.0` (final release from release candidate)

### Version Management

1. **Update `server/pyproject.toml`**: Change the version field manually
2. **Update lockfile**: Run `make sync` to ensure uv relocks the repository with the new version
3. **Create Git Tag**: Tag must match `agent-server-v{VERSION}` (e.g., `agent-server-v2.1.0`)
4. **Push Tag**: `git push origin agent-server-v2.1.0` triggers the release build

### Pre-release Guidelines

- Use `alpha` for early development versions
- Use `beta` for feature-complete but potentially unstable versions
- Use `rc` (release candidate) for versions ready for final testing
- Increment the numeric suffix for iterations (`.1`, `.2`, etc.)

## Release Process

### Standard Release (from `main` branch)

1. **Prepare the version and changelog**:

   ```bash
   # Edit server/pyproject.toml
   version = "2.1.0"

   # Update the lockfile after version change
   make sync
   ```

2. **Update the changelog**:

   - Convert the "Unreleased" section to a versioned section:

   ```markdown
   # Sema4.ai Agent Server 2.1.0 (2025-01-15)

   ## Agent Server

   ### Features

   - Your new features here
   ```

3. **Create PR and tag**:

   ```bash
   # Create PR with version bump and changelog updates
   git add server/pyproject.toml server/CHANGELOG.md
   git commit -m "Prepare release v2.1.0"
   git push origin your-version-bump-branch

   # After squash merge into main:
   git checkout main
   git pull origin main
   git tag agent-server-v2.1.0
   git push origin agent-server-v2.1.0
   ```

4. **Automatic deployment**: The tag push triggers the build and deployment automatically.

### Pre-Release (from `main` branch)

1. **Prepare the version and changelog**:

   ```bash
   # Edit server/pyproject.toml
   version = "2.1.0-alpha.1"

   # Update the lockfile after version change
   make sync
   ```

2. **Update the changelog**:

   - Convert the "Unreleased" section to a versioned section:

   ```markdown
   # Sema4.ai Agent Server 2.1.0-alpha.1 (2025-01-15)

   ## Agent Server

   ### Features

   - Your new features here
   ```

3. **Create PR and tag**:

   ```bash
   # Create PR with version bump and changelog updates
   git add server/pyproject.toml server/CHANGELOG.md
   git commit -m "Prepare pre-release v2.1.0-alpha.1"
   git push origin your-version-bump-branch

   # After squash merge into main:
   git checkout main
   git pull origin main
   git tag agent-server-v2.1.0-alpha.1
   git push origin agent-server-v2.1.0-alpha.1
   ```

4. **Automatic deployment**: The tag push triggers the build and deployment automatically.

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

# Run all PR checks (format, lint, typecheck, unit tests)
make check-pr
```

## CI/CD Pipelines

The project uses GitHub Actions for fully automated CI/CD. The main workflows are:

1. **Build & Test Agent Server for PRs** (`main-test.yml`):

   - **Triggers**: Automatically on pull requests and manual dispatch
   - **Actions**:
     - Static checks (linting, typechecking, formatting)
     - Unit tests across multiple platforms (Ubuntu, macOS, Windows)
     - Build and sign executables for all platforms
     - Integration tests
     - Deploy PR builds to CDN with PR-specific versioning
     - Send Slack notifications with download links

2. **Release - Build, Upload, and Notify** (`main-release-build.yml`):

   - **Triggers**: Automatically on git tag pushes matching `agent-server-v*`
   - **Actions**:
     - Build and sign executables for all platforms (Windows, macOS Intel/ARM, Linux)
     - Deploy to GitHub Releases and CDN
     - Create GitHub release with download links
   - **Requirements**: Tag must match the version in `server/pyproject.toml`

3. **Additional Workflows**:
   - **Agent CLI builds**: Separate workflows for CLI tooling
   - **Quality checks**: Linting and testing for quality benchmarking project

### Automatic Features

- **PR Builds**: Every PR gets a unique build deployed to CDN for testing
- **Slack Integration**: Automatic notifications with download links for all builds
- **Multi-platform**: All builds support Windows x64, macOS (Intel + ARM), and Linux x64
- **Code Signing**: Executables are automatically signed and notarized (macOS) or signed (Windows)

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
