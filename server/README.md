# Sema4.ai Agent Server

The Sema4.ai Agent Server provides the backend API services for both Sema4 Studio and Sema4 cloud.

**Latest Release:** `1.2.1-alpha.1`

## Documentation Content

- [Versioning and Publishing Sema4.ai Agent Server Packages](docs/publishing.md)
- [Developer Guide](docs/developer.md)
- [Agent Architectures](docs/cognitive-architectures.md)
- [LLM Configuration](docs/llms.md)
- [API Documentation](docs/api.md)
- [Authentication Guide](docs/auth.md)
- [Tools](docs/tools.md)

## Usage

To use the Agent Server in your project or as a backend, you may use it in several ways.

### Installing the Python Package

You can run the server by installing the wheel file from the [releases page](https://github.com/Sema4AI/agent-server/releases) and then executing the server via the command line. For example, to install the latest release, first download the appropriate wheel file, then run:

```bash
pip install agent_server-1.1.4-py3-none-any.whl # replace with the wheel file you downloaded
```

### Using a prebuilt Executable

You can also download a prebuilt executable for your platform from the [releases page](https://github.com/Sema4AI/agent-server/releases). For example, to download the latest release for Linux, you can run:

```bash
wget https://github.com/Sema4AI/agent-server/releases/download/v1.1.4/agent-server_v1.1.4_ubuntu_x64
chmod +x agent-server_v1.1.4_ubuntu_x64
./agent-server_v1.1.4_ubuntu_x64
```

### Command Flags

However you run the server, you can pass the following command line flags to configure the server:

- `--host`: The host to bind the server to. Default is `0.0.0.0`.
- `--port`: The port to run the HTTP server on. Default is `8000`.
- `--reload`: Enable auto-reload of the server on code changes, this is useful for development.
- `--parent-pid=<PID>`: Parent PID of the agent server. When the specified parent process exits, the agent server will also exit.
- `--use-data-dir-lock`: When set, uses a lock file to prevent multiple instances of the agent server from running in the same data directory. The data directory is defined by either `S4_AGENT_SERVER_HOME` or `SEMA4AI_STUDIO_HOME` environment variable.
- `--kill-lock-holder`: When set along with `--use-data-dir-lock`, kills any existing process that holds the lock file. Use with caution as it will forcefully terminate other running instances.

Note: the lock uses the SystemMutex in `sema4ai.common` which will create a file mutex that is released when the application exits (or the related Python variable has no references anymore). It's expected that `Studio` will use all the 3 newly added parameters to avoid leftover processes (and to force kill a running process).

### Data Directory Files

The agent server creates and manages the following files in the data directory (defined by either `S4_AGENT_SERVER_HOME` or `SEMA4AI_STUDIO_HOME` environment variable):

- `agent-server.lock`: A lock file which starts with `PID: <pid>\n`. The file may contain other contents, but only the `PID: <pid>\n` at the start of the file should be considered stable. This file is created when `--use-data-dir-lock` is enabled.

- `agent-server.pid`: A file containing information about the running server:
  - `port`: The port number the server is running on (the real port is written, even if the ephemeral port `0` was passed).
  - `pid`: Process ID of the agent server.
  - `base_url`: Base URL where the server can be accessed.
  - `lock_file`: Path to the lock file if `--use-data-dir-lock` is enabled, "<not used>" otherwise.

Upon startup, the agent server logs the data directory permissions and the data directory being used.

### Runtime Information

Upon startup, a message in the format `Agent Server running on: {base_url} (Press CTRL+C to quit)` will be written to the output, where `base_url` is something like `http://127.0.0.1:56342`. This string is stable, so clients that launch the agent server can rely on that output to detect the address to connect to.

Alternatively, clients can get the connection information from the `agent-server.pid` file contents. When using this approach, clients should verify that the `pid` in the file matches the process ID that currently holds the `agent-server.lock` to avoid racing conditions when getting the port being used.

### Environment Variables

You can also configure the server using environment variables. The following environment variables are supported:

- `OPENAI_API_KEY`: API key for OpenAI.
- `LANGCHAIN_TRACING_V2`: Enable LangChain tracing.
- `LANGCHAIN_PROJECT`: LangChain project name.
- `LANGCHAIN_API_KEY`: API key for LangChain.
- `AWS_ACCESS_KEY_ID`: AWS access key ID.
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key.
- `AWS_DEFAULT_REGION`: AWS default region.
- `POSTGRES_HOST`: Host for PostgreSQL.
- `POSTGRES_PORT`: Port for PostgreSQL.
- `POSTGRES_DB`: Database name for PostgreSQL.
- `POSTGRES_USER`: Username for PostgreSQL.
- `POSTGRES_PASSWORD`: Password for PostgreSQL.
- `SCARF_NO_ANALYTICS`: Disable Scarf analytics.
- `SEMA4AI_STUDIO_HOME`: Home directory for Agent Server.
- `SEMA4AI_STUDIO_LOG`: Log directory for Agent Server.
- `LOG_LEVEL`: Log level.
- `LOG_MAX_BACKUP_FILES`: Maximum number of log backup files.
- `S4_AGENT_SERVER_DB_TYPE`: Database type for the agent server (e.g., `sqlite`, `postgres`).
