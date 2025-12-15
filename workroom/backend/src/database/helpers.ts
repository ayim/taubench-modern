import { sql, type RawBuilder } from 'kysely';
import { Pool, type PoolConfig } from 'pg';
import type { MonitoringContext } from '../monitoring/index.js';

export const createPool = async ({
  monitoring,
  poolConfig,
}: {
  monitoring: MonitoringContext;
  poolConfig: Pick<PoolConfig, 'database' | 'host' | 'user' | 'password' | 'port' | 'max'>;
}): Promise<Pool> => {
  // Try SSL connection first
  const sslPool = new Pool({
    ...poolConfig,
    ssl: {
      rejectUnauthorized: false,
    },
  });

  try {
    // Test the connection
    const client = await sslPool.connect();
    client.release();

    monitoring.logger.info('Database connection established with SSL', {
      dbHost: poolConfig.host,
      dbName: poolConfig.database,
    });

    return sslPool;
  } catch (error) {
    // Clean up the failed pool
    await sslPool.end();

    if (error instanceof Error && error.message.includes('does not support SSL')) {
      monitoring.logger.info('Database does not support SSL: connecting without', {
        dbHost: poolConfig.host,
        dbName: poolConfig.database,
      });

      const noSslPool = new Pool({
        ...poolConfig,
        ssl: false,
      });

      // Verify the non-SSL connection works
      const client = await noSslPool.connect();
      client.release();
      return noSslPool;
    }

    throw error;
  }
};

export const omitProperties = <
  Item extends Record<string, unknown>,
  Keys extends Array<keyof Item>,
  KeysUnion extends Keys[number],
  Output extends Omit<Item, KeysUnion>,
>(
  obj: Item,
  properties: Keys,
): Output => {
  return Object.keys(obj).reduce((current, key) => {
    if (properties.includes(key)) return current;

    return {
      ...current,
      [key]: obj[key],
    };
  }, {} as Output);
};

export const pickProperties = <
  Item extends Record<string, unknown>,
  Keys extends Array<keyof Item>,
  KeysUnion extends Keys[number],
  Output extends Pick<Item, KeysUnion>,
>(
  obj: Item,
  properties: Keys,
): Output => {
  return Object.keys(obj).reduce((current, key) => {
    if (!properties.includes(key)) return current;

    return {
      ...current,
      [key]: obj[key],
    };
  }, {} as Output);
};

export const sqlNow = (): RawBuilder<string> => {
  return sql<string>`now()`;
};
