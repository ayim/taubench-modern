![Sema4.ia Gphpher Agent](assets/images/agent-gopher-250.png)


# Sema4.ai Golang Agent Client

This is the Official Sema4.ai Golang Agent Server Client. It is a Golang library that provides an interface to interact with 
the Sema4.ai Agent Server API.

## Installation
**Install As A Library**

Enable Go to download from a private repository by setting the `GOPRIVATE` environment variable.

- Linux / macos
  - Set env. var for the shell: `export GOPRIVATE=github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go`
  - Configure git to use SSH instead of HTTPS for private repositories: `git config --global url."git@github.com:".insteadOf "https://github.com/"`
- Windows
  - Just set env. variable: `GOPRIVATE=github.com/Sema4AI/*` and things will work in all of our go repos.
  - No git configs needed if you work on https


Install the library using `go get`:
```shell
go get github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go
```

## API Documentation

Run `make docs` to serve the project documentation locally.

## Project Standard Dependencies

- [Cobra](https://github.com/spf13/cobra) - For modern Go CLI interfaces.
- [Viper](https://github.com/spf13/viper) - For configuration management.
- [Testify](https://github.com/stretchr/testify) - For testing utilities.

## Project Structure

- `cmd/`: Application entry points (main packages)
- `pkg/`: Public libraries (importable by other projects)
- `internal/`: Internal application code (not exposed publicly)
- `config/`: Configuration files or modules
- `test/integration/`: Integration tests
- `test/unit/`: Unit tests

For more information on Golang project layout, see [golang-standards/project-layout](https://github.com/golang-standards/project-layout)

## Getting Started

1. **Initialize the Project:**
   - Run `make init-project` to install all necessary Go tools and tidy up the dependencies.

2. **Install Dependencies:**
   - Run `make deps` to install and update the project dependencies.

3. **Format Code:**
   - Use `make format` to automatically format all Go source files according to Go standards.

4. **Lint Code:**
   - Use `make lint` to check the code for any style issues or potential bugs. This requires `golangci-lint` to be installed, which is handled by `make init-project`.

5. **Run the Application:**
   - Use `make run` to build and run the application.

6. **Run Tests:**
   - Use `make test` to run the unit tests.
   - Use `make test-integration` to run the integration tests (requires integration tests to be set up).
   - Use `make test-all` to run all tests (unit and integration).

7. **Build the Application:**
   - Use `make build` to compile the application into a binary for your current OS and architecture.

8. **Create a Binary Distribution:**
   - Use `make dist` to create a `.tgz` and `.zip` archive of the application binary for your current OS and architecture. These archives will be placed in the `dist/` directory.

9. **Create Distributions for Multiple Platforms:**
   - Use `make dist-all` to create `.tgz` and `.zip` archives for the most common OS and architecture combinations (Linux, macOS, and Windows on amd64 and arm64 architectures). These archives will be placed in the `dist/` directory.

10. **Clean Up:**
    - Use `make clean` to remove previous build artifacts and test cache.

11. **Tidy Dependencies:**
    - Use `make tidy` to clean up the `go.mod` and `go.sum` files by removing unused dependencies.

12. **Serve Documentation:**
    - Use `make docs` to serve the project documentation locally.

## Usage

The folloing program is a simple example of how to use the client to get a list of agents from the server.

```go
package main

import (
   "fmt"
   ac "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
)

func main() {
   baseURL := "http://localhost:8100"
   client := ac.NewClient(baseURL)
   agents, err := client.GetAgents()
   if err != nil {
      panic(err)
   }
   for _, agent := range *agents {
      fmt.Println(agent.Name)
   }
}
```

## Verifying an Agent Server Endpoint

Run an Agent Server process or run Sema4.ai Agent Studio. Whichever you choose, you will need
to know the URL of the Agent Server endpoint. The default URL is http://localhost:8100.

You should have an Agent Server running. And you will need to know the port on which it is running. If you are running
Sema4.ai Studio the default port is 8000, otherwise it defaults to 8100.

You also need to pass in your OpenAI API Key as either a command line flag or an environment variable.

```shell
make test-integration
```

Or to use raw go commands:

```shell
go test ./test/integration --tags=integration

```

Both of the above commands will test a server running on the default port. If you are running the server on a different 
port, you can specify the port using the `S4_AGENT_SERVER_BASE_URL` environment variable, or use the 
`-base-url` flag.

**Use a command line flag:**

```shell
go test ./test/integration --tags=integration -base-url=http://localhost:8000 -openai-api-key=<your key here>
```

**Use an environment variable:**

```shell
S4_AGENT_SERVER_BASE_URL=http://localhost:8000 OPENAI_API_KEY=<your key here> </your>go test ./test/integration --tags=integration
```