# Backend Dockerfile
FROM python:3.11

ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT
ARG AGENT_SERVER_PORT=8000
# TODO need this for different OS. Hardcoded for now to unblock the platform team.
ARG AGENT_CLI_URL=https://cdn.sema4.ai/agent-cli/releases/v0.0.17/linux64/agent-cli
ARG ACTION_SERVER_URL=https://cdn.sema4.ai/action-server/releases/0.18.0/linux64/action-server

# Convert ARGs to ENVs
ENV AGENT_SERVER_PORT=${AGENT_SERVER_PORT}
ENV AGENT_CLI_URL=${AGENT_CLI_URL}
ENV ACTION_SERVER_URL=${ACTION_SERVER_URL}

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Download agent-cli and action-server
RUN curl -L ${AGENT_CLI_URL} -o /usr/local/bin/agent-cli && \
    chmod +x /usr/local/bin/agent-cli && \
    curl -L ${ACTION_SERVER_URL} -o /usr/local/bin/action-server && \
    chmod +x /usr/local/bin/action-server

# Set the working directory
WORKDIR /app

# Copy only dependencies
COPY pyproject.toml poetry.lock* ./

# Install all dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy the rest of application code
COPY sema4ai_agent_server/ sema4ai_agent_server/
COPY log_config.json log_config.json

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=1s --retries=3 CMD sh -c "curl -f http://localhost:$AGENT_SERVER_PORT/api/v1/health"

# Use a shell to ensure that the environment variable AGENT_SERVER_PORT is handled
ENTRYPOINT poetry run uvicorn sema4ai_agent_server.server:app --host 0.0.0.0 --port "$AGENT_SERVER_PORT"