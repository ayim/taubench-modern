#
# This container is built with hardcoded linux/amd64 action-server and agent-cli inside,
# therefore the image is also forced to linux/amd64 using the --platform flag.
#

ARG NODEJS_BASE_IMAGE="node:24.10.0-bookworm-slim@sha256:c0eadb278e6b0b608681b359291592692979133567710eaa703d6f989f33c6c1"

####################################################################################################
FROM --platform=linux/amd64 ${NODEJS_BASE_IMAGE} AS pruner

WORKDIR /build

COPY workroom .
RUN turbo_version="$(node -p 'require("./package.json").devDependencies.turbo')" \
    && npx "turbo@${turbo_version}" prune --docker --skip-infer \
    @sema4ai/mcp-runtime \
    ;

####################################################################################################
FROM --platform=linux/amd64 ${NODEJS_BASE_IMAGE} AS builder

WORKDIR /build

COPY --from=pruner /build/out/json/ .
RUN --mount=type=secret,id=npmrc,dst=/build/.npmrc \
    npm ci --include=dev --no-audit --no-fund --quiet

COPY --from=pruner /build/out/full/ .

RUN npx turbo build --filter=@sema4ai/mcp-runtime \
    && npm prune --omit=dev

####################################################################################################
FROM --platform=linux/amd64 ${NODEJS_BASE_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    procps \
    tini \
    unzip \
    && rm -rf /var/lib/apt/lists/*

ARG ACTION_SERVER_VERSION=2.17.0
ADD --chmod=755 https://cdn.sema4.ai/action-server/releases/${ACTION_SERVER_VERSION}/linux64/action-server /usr/local/bin/action-server

ARG USERNAME=mcp-runtime
# Directory for data persisted across container reboots
ENV SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR=/home/${USERNAME}/data
# Maximum Agent Package payload size
ENV SEMA4AI_MCP_RUNTIME_MAXIMUM_PACKAGE_SIZE="50mb"

RUN useradd -m ${USERNAME} \
    && mkdir -p \
        ${SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR}/sema4ai \
        /app \
    && chown -R ${USERNAME}:${USERNAME} \
        ${SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR} \
        /app \
    && ln -s ${SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR}/sema4ai /home/${USERNAME}/.sema4ai

USER ${USERNAME}
WORKDIR /app

COPY --chown=mcp-runtime:mcp-runtime --from=builder /build .

VOLUME ${SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR}
EXPOSE 8003
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "mcp-runtime/src/index.ts"]
