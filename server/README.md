# Sema4.ai Agent Server

The Sema4.ai Agent Server provides the backend API services for both Sema4 Studio and Sema4 cloud.

**Latest Release:** `1.2.5`

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

- `--host`: The host to bind the server to. Default is `127.0.0.1`.
- `--port`: The port to run the HTTP server on. Default is `8000`.
- `--parent-pid=<PID>`: Parent PID of the agent server. When the specified parent process exits, the agent server will also exit.
- `--use-data-dir-lock`: When set, uses a lock file to prevent multiple instances of the agent server from running in the same data directory. The data directory is defined by either `SEMA4AI_AGENT_SERVER_HOME` or `SEMA4AI_STUDIO_HOME` environment variable.
- `--kill-lock-holder`: When set along with `--use-data-dir-lock`, kills any existing process that holds the lock file. Use with caution as it will forcefully terminate other running instances.
- `--config-path=<PATH>`: Path to the configuration file. If not specified, the server follows a search order (see Configuration System below).
- `--data-dir=<PATH>`: Path to the data directory. Override the data directory specified in the configuration or environment variables.
- `--log-dir=<PATH>`: Path to the log directory. Override the log directory specified in the configuration or environment variables.
- `--show-config`: Show the current configuration (including all defaults) and exit. Displays defaults for any missing values along with usage information.
- `--export-config`: Export the current configuration as raw JSON without any additional text. Useful for shell redirection to create a configuration file.
- `--ignore-config`: Ignore the configuration file and use the defaults, CLI arguments, or environment variables.
- `--version`: Show the version of the agent server and exit.
- `--license`: Show the license information and exit.

Note: the lock uses the SystemMutex in `sema4ai.common` which will create a file mutex that is released when the application exits (or the related Python variable has no references anymore). It's expected that `Studio` will use all the 3 newly added parameters to avoid leftover processes (and to force kill a running process).

### Configuration System

The agent server uses a flexible configuration system that allows you to customize its behavior through a JSON configuration file, environment variables, or command-line arguments.

#### Configuration File

The configuration file is a JSON file that contains settings for various aspects of the server. The server looks for a configuration file in the following order:

1. Path specified by the `--config-path` command-line argument
2. Path specified by the `SEMA4AI_AGENT_SERVER_CONFIG_PATH` environment variable
3. `SEMA4AI_AGENT_SERVER_HOME/agent-server-config.json`
4. `SEMA4AI_STUDIO_HOME/agent-server-config.json`
5. Current working directory (`./agent-server-config.json`)

If no configuration file is found, server defaults will be used.

#### Viewing and Creating a Configuration File

To view the current configuration settings with explanatory text, run:

```bash
agent-server --show-config
```

To generate a template configuration file, you can use the `--export-config` parameter with shell redirection:

```bash
agent-server --export-config > agent-server-config.json
```

The `--export-config` parameter outputs only the raw JSON configuration, making it ideal for creating template files via shell redirection.

#### Configuration Structure

The configuration file is structured hierarchically, with each configuration class having its own section. For example:

```json
{
  "sema4ai_agent_server.constants.SystemPaths": {
    "data_dir": "/path/to/data",
    "log_dir": "/path/to/logs"
  },
  "sema4ai_agent_server.constants.SystemConfig": {
    "host": "127.0.0.1",
    "port": 8000,
    "db_type": "sqlite",
    "log_level": "INFO",
    "log_max_backup_files": 5,
    "log_file_size": 10485760
  }
}
```

#### Configuration Overrides

Configuration settings can be overridden in the following order of precedence (highest to lowest):

1. Command-line arguments (e.g., `--host`, `--port`)
2. Configuration file settings
3. Environment variables (see the Environment Variables section below)
4. Default values

#### System Paths Configuration

The `SystemPaths` configuration manages all file system paths used by the server:

- `data_dir`: Base directory for data storage
- `log_dir`: Directory for log files

Derived paths (not directly configurable):

- `vector_database_path`: Path to the vector database
- `domain_database_path`: Path to the domain database
- `log_file_path`: Path to the log file
- `upload_dir`: Directory for uploaded files
- `config_dir`: Directory for configuration files

#### System Configuration

The `SystemConfig` configuration manages general settings:

- `host`: Host address to bind the server to
- `port`: Port number to run the server on
- `db_type`: Database type (`sqlite` or `postgres`)
- `log_level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `log_max_backup_files`: Number of log rotation files
- `log_file_size`: Maximum log file size in bytes

### Data Directory Files

The agent server creates and manages the following files in the data directory (defined by either `SEMA4AI_AGENT_SERVER_HOME` or `SEMA4AI_STUDIO_HOME` environment variable):

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

You can configure the server using environment variables. We recommend using the `SEMA4AI_AGENT_SERVER_` prefixed variables for forward compatibility, but legacy variables are supported for backward compatibility.

#### Configuration

- `SEMA4AI_AGENT_SERVER_CONFIG_PATH`: Path to the configuration file.

#### Directories and Paths

- `SEMA4AI_AGENT_SERVER_DATA_DIR`: Data directory for the agent server.
  - Fallback: `SEMA4AI_AGENT_SERVER_HOME`, then `SEMA4AI_STUDIO_HOME`
- `SEMA4AI_AGENT_SERVER_HOME`: Home directory for the agent server.
  - Used as fallback for data directory if `SEMA4AI_AGENT_SERVER_DATA_DIR` is not set.
- `SEMA4AI_STUDIO_HOME`: Legacy home directory, used as fallback for data and log directories.

#### Logging

- `SEMA4AI_AGENT_SERVER_LOG_LEVEL`: Log level (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Fallback: `LOG_LEVEL`
- `SEMA4AI_AGENT_SERVER_LOG_DIR`: Log directory for the agent server.
  - Fallback: `SEMA4AI_STUDIO_LOG`, then `SEMA4AI_STUDIO_HOME`
- `SEMA4AI_AGENT_SERVER_LOG_MAX_BACKUP_FILES`: Maximum number of log backup files.
  - Fallback: `LOG_MAX_BACKUP_FILES`
- `SEMA4AI_AGENT_SERVER_LOG_FILE_SIZE`: Maximum log file size in bytes.
  - Fallback: `LOG_FILE_SIZE`

#### Database

- `SEMA4AI_AGENT_SERVER_DB_TYPE`: Database type (e.g., `sqlite`, `postgres`).
  - Fallback: `DB_TYPE`

#### PostgreSQL Configuration

- `SEMA4AI_AGENT_SERVER_POSTGRES_HOST`: Host for PostgreSQL.
  - Fallback: `POSTGRES_HOST`
- `SEMA4AI_AGENT_SERVER_POSTGRES_PORT`: Port for PostgreSQL.
  - Fallback: `POSTGRES_PORT`
- `SEMA4AI_AGENT_SERVER_POSTGRES_DB`: Database name for PostgreSQL.
  - Fallback: `POSTGRES_DB`
- `SEMA4AI_AGENT_SERVER_POSTGRES_USER`: Username for PostgreSQL.
  - Fallback: `POSTGRES_USER`
- `SEMA4AI_AGENT_SERVER_POSTGRES_PASSWORD`: Password for PostgreSQL.
  - Fallback: `POSTGRES_PASSWORD`

#### Authentication

- `SEMA4AI_AGENT_SERVER_AUTH_TYPE`: Authentication type for the server.
  - Fallback: `AUTH_TYPE`

#### File Management

- `SEMA4AI_AGENT_SERVER_FILE_MANAGEMENT_API_URL`: URL for file management API.
  - Fallback: `FILE_MANAGEMENT_API_URL`
- `SEMA4AI_AGENT_SERVER_FILE_MANAGER_TYPE`: Type of file manager to use (e.g., `local`, `cloud`).

#### Telemetry

- `SEMA4AI_AGENT_SERVER_OTEL_COLLECTOR_URL`: URL for OpenTelemetry collector.
  - Fallback: `OTEL_COLLECTOR_URL`

#### Third-party Services

- `OPENAI_API_KEY`: API key for OpenAI.
- `LANGCHAIN_TRACING_V2`: Enable LangChain tracing.
- `LANGCHAIN_PROJECT`: LangChain project name.
- `LANGCHAIN_API_KEY`: API key for LangChain.
- `AWS_ACCESS_KEY_ID`: AWS access key ID.
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key.
- `AWS_DEFAULT_REGION`: AWS default region.
- `SCARF_NO_ANALYTICS`: Disable Scarf analytics.

#### Configuration Customization and Best Practices

The configuration system is designed to be flexible and extensible. Here are some best practices for customizing your configuration:

1. **Start with a template**: Use the `--show-config` flag to generate a complete configuration file with all default values. This gives you a starting point for customization.

2. **Partial updates**: You don't need to specify all configuration settings in your file. The system will use defaults for any unspecified settings, so you can create a minimal configuration file with just the settings you want to override.

3. **Environment-specific configurations**: Create different configuration files for different environments (development, staging, production) and specify the path using the `--config-path` flag or `SEMA4AI_AGENT_SERVER_CONFIG_PATH` environment variable.

4. **Security considerations**: For sensitive settings like API keys, prefer using environment variables over storing them in the configuration file, especially in shared or version-controlled environments.

5. **Validation**: The configuration system validates settings when loading them, so if you provide an invalid value, you'll get an error message explaining the issue.

#### Advanced Configuration

For more advanced use cases, the agent server supports custom configuration classes through the `agent_server_types.configurations` module. Developers extending the agent server can create their own configuration classes by subclassing `Configuration` or `MapConfiguration`, and the configuration system will automatically discover and load them.

These custom configurations will be included in the output of the `--show-config` flag and can be overridden in the configuration file just like the built-in configurations.

#### Configuration Troubleshooting

If you encounter issues with your configuration, here are some troubleshooting steps:

1. **Verify configuration loading**: Use the `--show-config` flag to see what configuration is being loaded. This will help identify if your custom settings are being applied correctly.

2. **Check log output**: The server logs information about configuration loading during startup. Check the logs for any warnings or errors related to configuration.

3. **Debug with `--ignore-config`**: If you suspect an issue with your configuration file, use the `--ignore-config` flag to run with default settings.

4. **Path issues**: Ensure that any paths specified in the configuration (data_dir, log_dir) are absolute paths or relative to the current working directory.

5. **Permission issues**: Check that the server has proper permissions to read the configuration file and write to the specified data and log directories.

#### Example: Customizing Configuration

Here's a complete example of customizing the agent server configuration:

1. First, generate a template configuration file:

```bash
agent-server --show-config > my-config.json
```

2. Edit the configuration file to customize settings:

```json
{
  "sema4ai_agent_server.constants.SystemConfig": {
    "host": "0.0.0.0",
    "port": 9000,
    "log_level": "DEBUG"
  },
  "sema4ai_agent_server.constants.SystemPaths": {
    "data_dir": "/var/lib/sema4ai/data",
    "log_dir": "/var/log/sema4ai"
  }
}
```

3. Start the server with your custom configuration:

```bash
agent-server --config-path my-config.json
```

This will start the server listening on all interfaces (0.0.0.0) on port 9000, with DEBUG level logging, storing data in `/var/lib/sema4ai/data` and logs in `/var/log/sema4ai`.
