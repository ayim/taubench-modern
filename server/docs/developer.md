# Sema4.ai Agent Server Developer Guide

## Quickstart with Docker

This project supports a Docker-based setup, streamlining installation and execution. It automatically sets up the backend service with Postgres using docker-compose.

1. **Prerequisites:**  
   Ensure you have `Docker` and `docker-compose` installed on your system.

2. **Clone the Repository:**  
   Obtain the project files by cloning the repository.

   ```shell
   git clone https://github.com/Sema4AI/agent-server.git
   cd agent-server
   ```

3. **Set Up Environment Variables:**  
   Create a `.env` file in the root directory of the project by copying `.env.example` as a template, and add the
   following environment variables:

   ```shell
   # At least one language model API key is required
   OPENAI_API_KEY=sk-...
   # LANGCHAIN_TRACING_V2=true
   # LANGCHAIN_API_KEY=...

   # Setup for Postgres. Docker compose will use these values to set up the database.
   POSTGRES_PORT=5432
   POSTGRES_DB=agentserver
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=...
   ```

   Replace `sk-...` with your OpenAI API key and `...` with your LangChain API key.

4. **Run with Docker Compose:**  
   In the root directory of the project, execute:

   ```shell
   docker compose up
   ```

   This command builds the Docker image for the backend from its Dockerfile and starts all necessary services, including Postgres.

5. **Rebuilding After Changes:**  
   If you make changes to the backend, rebuild the Docker images to reflect these changes. Run:

   ```shell
   docker compose up --build
   ```

This command rebuilds the images with your latest changes and restarts the services.

## Quickstart without Docker

1. **Prerequisites**
   The following instructions assume you have Python 3.11+ installed on your system. We strongly recommend using a virtual environment to manage dependencies.

   For example, if you are using `pyenv`, you can create a new virtual environment with:

   ```shell
   pyenv install 3.11
   pyenv virtualenv 3.11 agentserver
   pyenv activate agentserver
   ```

   If you are using `anaconda`, you can create a new virtual environment with:

   ```shell
   conda create -n agentserver python=3.11 pip
   conda activate agentserver
   ```

   Once your Python environment is set up, you can install the project dependencies:

   The backend service uses [poetry](https://python-poetry.org/docs/#installation) to manage dependencies.

   ```shell
   pip install poetry
   pip install langchain-community
   ```

2. **Install Postgres and the Postgres Vector Extension**

   ```shell
   brew install postgresql pgvector
   brew services start postgresql
   ```

3. **Configure persistence layer**

   The backend uses Postgres for saving agent configurations and chat message history.
   In order to use this, you need to set the following environment variables:

   ```shell
   export POSTGRES_HOST=localhost
   export POSTGRES_PORT=5432
   export POSTGRES_DB=agentserver
   export POSTGRES_USER=postgres
   export POSTGRES_PASSWORD=...
   ```

4. **Create the database**

   ```shell
   createdb agentserver
   ```

5. **Connect to the database and create the `postgres` role**

   ```shell
   psql -d agentserver
   ```

   ```sql
   CREATE ROLE postgres WITH LOGIN SUPERUSER CREATEDB CREATEROLE;
   ```

6. **Install backend dependencies**

   ```shell
   poetry install
   ```
