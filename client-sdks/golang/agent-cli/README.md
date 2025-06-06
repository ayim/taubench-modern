## Getting started

To use the latest release, download the binary for your platform:

- [https://cdn.sema4.ai/agent-cli/releases/latest/linux64/agent-cli](https://cdn.sema4.ai/agent-cli/releases/latest/linux64/agent-cli)
- [https://cdn.sema4.ai/agent-cli/releases/latest/windows64/agent-cli.exe](https://cdn.sema4.ai/agent-cli/releases/latest/windows64/agent-cli.exe)
- [https://cdn.sema4.ai/agent-cli/releases/latest/macos64/agent-cli](https://cdn.sema4.ai/agent-cli/releases/latest/macos64/agent-cli)

## Usage

To find all available commands and options, run:

```bash
./agent-cli --help
```

Below are some common commands.

#### Check version

```bash
./agent-cli --version
```

#### List all existing agents in agent-server

```bash
./agent-cli project list
```

Outputs a list of all existing agents in JSON format to stdout.

#### Create a new project (empty)

```bash
./agent-cli project new
```

Creates a minimal project. Accepts optional `--path`.

#### Create a new project from agent

```bash
./agent-cli project export --agent <name>
```

Creates a project from exported Sema4.ai Studio agent. Accepts optional `--path` and `--agent-server-url` (default is http://localhost:8100).

#### Build a package from project

```bash
./agent-cli package build
```

Creates an agent package that can be deployed. Needs to be run inside an agent project (where agent-spec.yaml is located). Accepts optional `input-dir`, `--output-dir` and `--name` (e.g. `--name my-package.zip`) and `--overwrite`.

#### Extract a project from package

```bash
./agent-cli package extract --package <path_to_package>
```

Creates a project from an agent package. Accepts optional `--output-dir` and `--overwrite`.

#### Generate package's metadata

```bash
./agent-cli package metadata --package <path_to_package>
```

Generates JSON metadata for an agent package. Accepts optional `--output-file`.

## Development

1. Add environment variable for go to get private packages: `$ go env -w GOPRIVATE=github.com/<your github handle>/*`
2. Install development environment:

   - You can use [the developer setup scripts](./developer/README.md)
   - OR
   - Install the following on your OS:
     - go=1.23.x
     - gh=2.62.x (depending on your git setup)
     - git=2.46.x (depending on your git setup)

3. If you use GitHub with SSH keys with `git@`
   - NOTE: If you are are using HTTPS this will very much break your Git setup. ⚠️
   - Make sure you can authenticate to GitHub (use SSH keys)
   - Setup Go to use SSH keys for GitHub authentication: `$ git config --global url."git@github.com:".insteadOf "https://github.com/"`
   - Test by getting agent server client: `$ go get github.com/Sema4AI/agent-client-go`

### Build the CLI (Macos / Linux)

```bash
cd cli

# Load dependencies
go mod tidy

# Linux / macos
go build -o build/agent-cli
```

### Build the CLI (Windows)

```bash
cd cli

# Load dependencies
go mod tidy

# Windows
go build -o build\agent-cli.exe
```

### Testing

#### Running Smoke Tests

The CLI includes smoke tests to verify basic functionality. The tests can use either a pre-built binary or the default build location.

Using default build location:

```bash
# First build the CLI
# Linux/macOS:
go build -o build/agent-cli

# Windows:
go build -o build\agent-cli.exe

# Then run the tests
go test -v
```

Using a specific binary:

```bash
# Linux/macOS:
go test -v -binary=./path/to/agent-cli

# Windows:
go test -v -binary=.\path\to\agent-cli.exe
```

The smoke tests will:

1. Locate the CLI binary (either from -binary flag or default build location)
2. Run a series of basic command tests
3. Output detailed logs of each command execution

#### Writing New Tests

New smoke tests can be added to `cli/test/smoke_test.go`. The tests use a table-driven pattern for easy addition of new test cases. Example:

```go
func TestYourFeature(t *testing.T) {
    tests := []commandTest{
        {
            name:    "your test case",
            args:    []string{"command", "--flag"},
            wantErr: false,
        },
    }
    runCommandTests(t, tests)
}
```

## Releasing Agent CLI

1. Update [CHANGELOG.md](/cli/CHANGELOG.md) actively while developing under the `Unreleased` -section
   - Remember to write the changelog items taht affect the user of the tool (Control Room, Studio and SDK -extension)
1. On release update the version in [/cli/common/version.go](/cli/common/version.go)
1. Update the [CHANGELOG.md](/cli/CHANGELOG.md) with the version number and date.
1. Commit to `develop` -branch
1. Go to: [GitHub Releases](https://github.com/Sema4AI/agents-spec/releases)
1. `Draft a new release` > `Choose a tag` > `Create a new tag` > `Generate release notes`
   - Tag naming is: `sema4ai-agent_cli-<the version in version.go>`
1. Create release as pre-release or latest (has not affect other than visual in GitHub)
1. The above triggers [Agent CLI Release](https://github.com/Sema4AI/agents-spec/actions/workflows/agent-server-release.yaml) -gha that builds and publishes the executable
1. The releases end-up in S3 CDN:
   - Windows: https://cdn.sema4.ai/agent-cli/releases/v1.0.0/windows64/agent-cli.exe
   - Mac: https://cdn.sema4.ai/agent-cli/releases/v1.0.0/macos-arm64/agent-cli
   - Linux: https://cdn.sema4.ai/agent-cli/releases/v1.0.0/linux64/agent-cli
