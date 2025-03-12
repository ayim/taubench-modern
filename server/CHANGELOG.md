# Unreleased

- Added new command line parameters:

  - `--parent-pid=<PID>`: Parent PID of the agent server. When the specified parent process exits,
    the agent server will also exit.

  - `--use-data-dir-lock`: When set, uses a lock file to prevent multiple instances of the agent server
    from running in the same data directory. The data directory is defined by either
    S4_AGENT_SERVER_HOME or SEMA4AI_STUDIO_HOME environment variable.

  - `--kill-lock-holder`: When set along with --use-data-dir-lock, kills any existing process that holds
    the lock file. Use with caution as it will forcefully terminate other running instances.

  - Note: the lock uses the SystemMutex in `sema4ai.common` which will create a file mutex which
    is released when the application exits (or the related python variable has no references anymore).

  - It's expected that `Studio` will use all the 3 newly added parameters to avoid leftover processes
    (and to force kill a running process).

- A lock file which starts with `PID: <pid>\n` is written to the `data-dir/agent-server.lock`. The file
  may contain other contents, but only the `PID: <pid>\n` at the start of the file should be considered stable.

- Added `agent-server.pid` file in the data directory that contains:

  - `port`: The port number the server is running on (the real port is written, even if the ephemeral port `0` was passed).
  - `pid`: Process ID of the agent server.
  - `base_url`: Base URL where the server can be accessed.
  - `lock_file`: Path to the lock file if `--use-data-dir-lock` is enabled, "<not used>" otherwise.

- Upon startup, log the data directory permissions (and print data directory being used).

- Upon startup a message as `Agent Server running on: {base_url} (Press CTRL+C to quit)` will be written to the output,
  where `base_url` is something as `http://127.0.0.1:56342`
  (this string should be stable, so, clients that launch the agent server should be able to rely on that output to detect the
  address to connect to from the output written by the agent server -- another alternative for clients to get the
  address to connect to is using the `agent-server.pid` file contents, but then they need to be careful to check
  that the `pid` of that file is the same pid which currently holds the `agent-server.lock`
  to make sure there are no racing conditions getting the port being used).
