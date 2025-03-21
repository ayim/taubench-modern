FROM ubuntu:22.04

# Arguments and Environment Variables
ARG AGENT_SERVER_VERSION
ARG AGENT_RELEASE_CHANNEL
ARG AGENT_SERVER_PORT=8000
# TODO need this for different OS. Hardcoded for now to unblock the platform team.
ARG AGENT_CLI_URL=https://cdn.sema4.ai/agent-cli/releases/v0.0.17/linux64/agent-cli
ARG ACTION_SERVER_URL=https://cdn.sema4.ai/action-server/releases/0.18.0/linux64/action-server

ENV AGENT_SERVER_VERSION=${AGENT_SERVER_VERSION}
ENV AGENT_SERVER_PORT=${AGENT_SERVER_PORT}
ENV AGENT_CLI_URL=${AGENT_CLI_URL}
ENV ACTION_SERVER_URL=${ACTION_SERVER_URL}
ENV AGENT_RELEASE_CHANNEL=${AGENT_RELEASE_CHANNEL}

# Install necessary dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Download agent-cli and action-server
RUN curl -L ${AGENT_CLI_URL} -o /usr/local/bin/agent-cli && \
    chmod +x /usr/local/bin/agent-cli && \
    curl -L ${ACTION_SERVER_URL} -o /usr/local/bin/action-server && \
    chmod +x /usr/local/bin/action-server

# Set the working directory
WORKDIR /app

# Download the agent-server binary
RUN curl -L "https://cdn.sema4.ai/agent-server/${AGENT_RELEASE_CHANNEL}/${AGENT_SERVER_VERSION}/linux_x64/agent-server" \
    -o /usr/local/bin/agent-server && \
    chmod +x /usr/local/bin/agent-server

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=1s --retries=3 \
    CMD curl -f http://localhost:${AGENT_SERVER_PORT}/api/v1/health || exit 1

# Run the agent-server
CMD ["/bin/sh", "-c", "agent-server --host 0.0.0.0 --port ${AGENT_SERVER_PORT}"]
