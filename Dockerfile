# Multi-stage Dockerfile for Agent Server - Optimized for Production
# Stage 1: Build stage - Use golang image as base (more optimized than Ubuntu)
FROM golang:1.23-bookworm AS builder

# Install system dependencies needed for building
RUN apt-get update && \
    apt-get install -y \
        curl \
        build-essential \
        git \
        ca-certificates \
        make \
        python3 \
        python3-pip \
        && rm -rf /var/lib/apt/lists/*

# Install uv globally using pip (more reliable for Docker)
RUN pip3 install uv --break-system-packages

# Set working directory
WORKDIR /build

# Copy workspace configuration first (better caching)
COPY pyproject.toml uv.lock Makefile ./

# Copy only the source packages needed for the workspace build
COPY core/ core/
COPY server/ server/
COPY architectures/ architectures/

# Copy scripts needed for build
COPY scripts/build_exe.py scripts/build_exe.py
COPY scripts/entrypoint.sh scripts/entrypoint.sh

# Build the executable using make commands (Go is already in PATH from golang image)
RUN make sync && make build-exe

#region Runtime
# Stage 2: Minimal Debian runtime with required libraries
FROM debian:12-slim AS runtime

# Install minimal runtime dependencies needed for PyInstaller executables
RUN apt-get update && \
    apt-get install -y \
        curl \
        ca-certificates \
        zlib1g \
        poppler-utils \
        && rm -rf /var/lib/apt/lists/* && \
    # Create non-root user for security
    useradd -r -s /bin/false -m -d /app agentserver

# Arguments and Environment Variables
ARG AGENT_SERVER_PORT=8000
ENV AGENT_SERVER_PORT=${AGENT_SERVER_PORT}
ENV SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true
ENV SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true
ENV SEMA4AI_OPTIMIZE_FOR_CONTAINER=1

# Set the working directory
WORKDIR /app

# Copy the built executable from builder stage
COPY --from=builder /build/dist/agent-server /usr/local/bin/agent-server
COPY --from=builder /build/scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /usr/local/bin/agent-server

# Change to non-root user
USER agentserver

# Expose port
EXPOSE ${AGENT_SERVER_PORT}

# Healthcheck for Docker-Compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${AGENT_SERVER_PORT}/api/v2/health || exit 1

# Run the agent-server
ENTRYPOINT ["/app/entrypoint.sh"]
#endregion
