import { parseEnvVariable, parseEnvVariableInteger } from '@sema4ai/shared-utils';
import type { PoolConfig } from 'pg';

const HTTP_API_PORT = 8003;
const GRACEFUL_SHUTDOWN_TIMEOUT_IN_SECONDS = 10;
const POSTGRES_SCHEMA = 'mcp_runtime';
const MIGRATIONS_LOCK_TABLE = 'mcp_runtime_migration_lock';
const MIGRATIONS_RECORDS_TABLE = 'mcp_runtime_migrations';

export type Configuration = {
  httpApiPort: number;
  gracefulShutdownTimeoutInSeconds: number;
  persistentDataDirectory: string;
  maxServerCount: number;
  maxPackageSize: string;
  minServerPort: number;
  serverHttpUrl: string;
  database: {
    schema: string;
    poolConfiguration: Pick<PoolConfig, 'database' | 'host' | 'user' | 'password' | 'port' | 'max'>;
    migrations: {
      lockTable: string;
      recordsTable: string;
    };
  };
};

export const getConfiguration = (): Configuration => {
  return {
    // Port to expose the Express HTTP API on
    httpApiPort: HTTP_API_PORT,
    // Amount of time (in seconds) to wait for the server to gracefully shut down
    gracefulShutdownTimeoutInSeconds: GRACEFUL_SHUTDOWN_TIMEOUT_IN_SECONDS,
    // Persistent directory for storing deployment artifacts
    persistentDataDirectory: parseEnvVariable('SEMA4AI_MCP_RUNTIME_PERSISTENT_DATA_DIR'),
    // Maximum number of Action Servers we allow to run and the lowest port we
    // allocate. Note: The ports need not be exposed - the servers are accessed
    // through a reverse proxy (workroom/mcp-runtime/src/lib/proxy.ts)
    maxServerCount: 10,
    minServerPort: 20000,
    // This is the maximum allowed size for an Agent Package upload
    maxPackageSize: parseEnvVariable('SEMA4AI_MCP_RUNTIME_MAXIMUM_PACKAGE_SIZE'),
    // This server's HTTP URL - used for generating URLs for Action Servers
    serverHttpUrl: parseEnvVariable('SEMA4AI_MCP_RUNTIME_SERVER_HOST_OVERRIDE'),
    // PostgreSQL database connection details
    database: {
      schema: POSTGRES_SCHEMA,
      poolConfiguration: {
        database: parseEnvVariable('POSTGRES_DB'),
        host: parseEnvVariable('POSTGRES_HOST'),
        password: parseEnvVariable('POSTGRES_PASSWORD'),
        port: parseEnvVariableInteger('POSTGRES_PORT'),
        user: parseEnvVariable('POSTGRES_USER'),
        max: 10, // Maximum number of connections
      },
      migrations: {
        lockTable: MIGRATIONS_LOCK_TABLE,
        recordsTable: MIGRATIONS_RECORDS_TABLE,
      },
    },
  };
};
