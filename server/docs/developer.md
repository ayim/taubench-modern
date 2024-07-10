# Sema4.ai Agent Server Developer Guide

## Quickstart with Docker

This project supports a Docker-based setup, streamlining installation and execution. It automatically builds images for 
the frontend and backend and sets up Postgres using docker-compose.


1. **Prerequisites:**  
    Ensure you have Docker and docker-compose installed on your system.


2. **Clone the Repository:**  
   Obtain the project files by cloning the repository.

   ```
   git clone https://github.com/langchain-ai/opengpts.git
   cd opengpts
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
   POSTGRES_DB=opengpts
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=...
   ```

   Replace `sk-...` with your OpenAI API key and `...` with your LangChain API key.


4. **Run with Docker Compose:**  
   In the root directory of the project, execute:

   ```
   docker compose up
   ```

   This command builds the Docker images for the frontend and backend from their respective Dockerfiles and starts all 
   necessary services, including Postgres.

5. **Access the Application:**  
   With the services running, access the frontend at [http://localhost:5173](http://localhost:5173), substituting `5173` with the 
   designated port number.


6. **Rebuilding After Changes:**  
   If you make changes to either the frontend or backend, rebuild the Docker images to reflect these changes. Run:
   ```
   docker compose up --build
   ```
   This command rebuilds the images with your latest changes and restarts the services.


## Quickstart without Docker

**Prerequisites**
The following instructions assume you have Python 3.11+ installed on your system. We strongly recommend using a virtual 
environment to manage dependencies.

For example, if you are using `pyenv`, you can create a new virtual environment with:
```shell
pyenv install 3.11
pyenv virtualenv 3.11 opengpts
pyenv activate opengpts
```

Once your Python environment is set up, you can install the project dependencies:

The backend service uses [poetry](https://python-poetry.org/docs/#installation) to manage dependencies.

```shell 
pip install poetry
pip install langchain-community
```

**Install Postgres and the Postgres Vector Extension**
```
brew install postgresql pgvector
brew services start postgresql
```

**Configure persistence layer**

The backend uses Postgres for saving agent configurations and chat message history.
In order to use this, you need to set the following environment variables:

```shell
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=opengpts
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=...
```

**Create the database**
```shell
createdb opengpts
```

**Connect to the database and create the `postgres` role**
```shell
psql -d opengpts
```

```sql
CREATE ROLE postgres WITH LOGIN SUPERUSER CREATEDB CREATEROLE;
```

**Install Golang Migrate**

Database migrations are managed with [golang-migrate](https://github.com/golang-migrate/migrate). 

On MacOS, you can install it with `brew install golang-migrate`. Instructions for other OSs or the Golang toolchain, 
can be found [here](https://github.com/golang-migrate/migrate/blob/master/cmd/migrate/README.md#installation).

Once `golang-migrate` is installed, you can run all the migrations with:
```shell
make migrate
```

This will enable the backend to use Postgres as a vector database and create the initial tables.


**Install backend dependencies**
```shell
cd backend
poetry install
```

