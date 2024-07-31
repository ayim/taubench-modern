# Backend Dockerfile
FROM python:3.11

ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN wget -O golang-migrate.deb https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.${TARGETOS}-${TARGETARCH}${TARGETVARIANT}.deb \
    && dpkg -i golang-migrate.deb \
    && rm golang-migrate.deb

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
COPY . .

# Install any missing dependencies
RUN poetry install --no-interaction --no-ansi

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --start-interval=1s --retries=3 CMD [ "curl", "-f", "http://localhost:8100/health" ]

ENTRYPOINT [ "poetry", "run", "uvicorn", "sema4ai_agent_server.server:app", "--host", "0.0.0.0", "--port", "8100" ]