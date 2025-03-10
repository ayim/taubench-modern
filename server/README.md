# Sema4.ai Agent Server

The Sema4.ai Agent Server provides the backend API services for both Sema4 Studio and Sema4 cloud.

**Latest Release:** `1.1.4-alpha.88`

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
