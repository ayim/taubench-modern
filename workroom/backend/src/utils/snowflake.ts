/**
 * Snowflake user identity header
 * @example
 *  "perry@sema4.ai"
 * @example
 *  "perry"
 */
export const SNOWFLAKE_AUTH_HEADER = 'sf-context-current-user';

/**
 * Static value to use for authority "issuer" when handling Snowflake
 * user identities in the database. Do not change - previous sessions
 * and identities will disconnect.
 */
export const SNOWFLAKE_AUTHORITY = 'https://app.snowflake.com';
