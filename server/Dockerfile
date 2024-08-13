# Backend Dockerfile
FROM python:3.11

ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT
ARG AGENT_SERVER_PORT=8100

# Convert ARG to ENV
ENV AGENT_SERVER_PORT=${AGENT_SERVER_PORT}

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set the working directory
WORKDIR /app

# Copy only dependencies
COPY pyproject.toml poetry.lock* ./

# Install all dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy the rest of application code
COPY sema4ai_agent_server/ sema4ai_agent_server/
COPY log_config.json log_config.json

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=1s --retries=3 CMD sh -c "curl -f http://localhost:$AGENT_SERVER_PORT/health"

# Use a shell to ensure that the environment variable AGENT_SERVER_PORT is handled
ENTRYPOINT poetry run uvicorn sema4ai_agent_server.server:app --host 0.0.0.0 --port "$AGENT_SERVER_PORT"