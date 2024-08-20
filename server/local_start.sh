#!/bin/zsh

# Function to print usage information
print_usage() {
    echo "Usage: $0 [-d <postgres|sqlite>]"
    echo "  -d: Specify the database type (postgres or sqlite). Default is postgres."
    echo "  -h: Display this help message."
}

# Set default database type
DB_TYPE=${S4_AGENT_SERVER_DB_TYPE:-postgres}

# Parse command-line options
while getopts ":d:h" opt; do
    case ${opt} in
        d )
            DB_TYPE=$OPTARG
            ;;
        h )
            print_usage
            exit 0
            ;;
        \? )
            echo "Invalid option: $OPTARG" 1>&2
            print_usage
            exit 1
            ;;
        : )
            echo "Invalid option: $OPTARG requires an argument" 1>&2
            print_usage
            exit 1
            ;;
    esac
done

# Validate DB_TYPE
if [[ "$DB_TYPE" != "postgres" && "$DB_TYPE" != "sqlite" ]]; then
    echo "Invalid database type. Please use 'postgres' or 'sqlite'."
    print_usage
    exit 1
fi

export S4_AGENT_SERVER_DB_TYPE=$DB_TYPE
export SCARF_NO_ANALYTICS=true
# PostgreSQL-specific environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5433
export POSTGRES_DB=postgres
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

if [ "$DB_TYPE" = "postgres" ]; then
    echo "🚀 Starting PostgreSQL service..."
    docker compose up -d postgres

    if [ $? -eq 0 ]; then
        echo "✅ PostgreSQL started successfully."
    else
        echo "❌ Failed to start PostgreSQL service. Please check Docker Compose logs."
        exit 1
    fi

    sleep 1

    echo "📦 Running database migrations..."
    make migrate-postgres
else
    echo "🔧 Using SQLite database..."
    # No additional setup needed for SQLite
fi

# Setup and start the agent server
echo "🔧 Setting up the Agent Server..."

echo "📦 Installing dependencies..."
poetry install

# Start the backend server using uvicorn
echo "🚀 Starting the Agent Server..."
poetry run uvicorn sema4ai_agent_server.server:app --host 0.0.0.0 --port 8100 --reload
