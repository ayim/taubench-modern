import z from 'zod';
import type { Configuration } from '../configuration.js';

type LogMethod<Attributes extends LogAttributes> = (text: string, data?: Partial<Attributes>) => void;

export interface LogAttributes {
  agentServerUserId: string;
  agentServerUserSub: string;
  authMode: Configuration['auth']['type'];
  authSkip: boolean;
  contentDispositionType: string;
  count: number;
  dbHost: string;
  dbName: string;
  dbPort: number;
  dbSchema: string;
  error?: Error;
  errorCause: string;
  errorMessage: string;
  errorName: string;
  errorStack: string;
  expiresInMin: number;
  fileId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  logLevel: LogSeverity;
  migrationDirection: string;
  migrationName: string;
  migrationStatus: string;
  objectStorageBucketName: string;
  oidcIssuer: string;
  oidcRedirectUrl: string;
  oidcScopes: string;
  oidcUserId: string;
  port: number;
  processSignal: string;
  requestMethod: string;
  requestUrl: string;
  sessionId: string;
  snowflakeUserId: string;
  status: number;
  statusText: string;
  tenantId: string;
  /**
   * Internal SPAR user ID
   */
  userId: string;
  userRole: string;
}

interface DebugLogAttributes extends LogAttributes {
  dbHost: string;
  dbName: string;
  dbPort: number;
  dbSchema: string;
  emailAddress: string;
  oidcClaims: string;
  oidcHasRefresh: boolean;
}

export interface LoggingContext {
  debug: LogMethod<DebugLogAttributes>;
  error: LogMethod<LogAttributes>;
  info: LogMethod<LogAttributes>;
}

export interface MonitoringContext {
  logger: LoggingContext;
}

export type LogSeverity = z.infer<typeof LogSeverity>;
export const LogSeverity = z.preprocess(
  (val) => (typeof val === 'string' ? val.toUpperCase() : val),
  z.enum(['DEBUG', 'INFO', 'ERROR']),
);

const SEVERITY_VALUE: { [K in LogSeverity]: number } = {
  DEBUG: 20,
  ERROR: 40,
  INFO: 30,
};

const buildLogMethod = <Attributes extends LogAttributes>(
  severity: LogSeverity,
  { minimumSeverity }: { minimumSeverity: LogSeverity },
): LogMethod<Attributes> => {
  const currentLevel = SEVERITY_VALUE[severity];
  const minLevel = SEVERITY_VALUE[minimumSeverity];
  const shouldOutput = currentLevel >= minLevel;

  return (text: string, data: Partial<Attributes> = {}): void => {
    if (!shouldOutput) return;

    const attributes: Partial<Attributes> = { ...data };

    if (data.error) {
      Object.assign(attributes, {
        errorMessage: data.error.message,
        errorName: data.error.name,
        errorStack: data.error.stack,
      });

      if (data.error.cause instanceof Error) {
        attributes.errorCause = formatErrorCause(data.error.cause);
      }

      delete attributes.error;
    }

    writeLogToStdout({
      attributes,
      severity,
      text,
    });
  };
};

const formatErrorCause = (error: Error, depth: number = 0): string => {
  const indent = '  '.repeat(depth);

  let result = `${indent}Error: ${error.message}\n`;

  if (error.stack) {
    const stackLines = error.stack.split('\n').slice(3);
    result += stackLines.map((line) => `${indent}${line.trim()}`).join('\n') + '\n';
  }

  if ('cause' in error && error.cause instanceof Error) {
    result += `${indent}Caused by:\n${formatErrorCause(error.cause, depth + 1)}`;
  } else if ('cause' in error && error.cause) {
    result += `${indent}Caused by: ${error.cause}\n`;
  }

  return result;
};

const writeLogToStdout = ({
  attributes,
  severity,
  text,
}: {
  attributes: Partial<LogAttributes>;
  severity: LogSeverity;
  text: string;
}): void => {
  const formattedAttributes = Object.keys(attributes)
    .map((key) => `${key}="${attributes[key as keyof Partial<LogAttributes>]}"`)
    .join(' ');

  const output = `${new Date().toISOString()} [${severity}] ${text} ${formattedAttributes.length > 0 ? `(${formattedAttributes})` : ''}`;

  if (['ERROR'].includes(severity)) {
    // eslint-disable-next-line no-console
    console.error(output);
  } else {
    // eslint-disable-next-line no-console
    console.log(output);
  }
};

export const createMonitoringContext = ({ logLevel = 'INFO' }: { logLevel?: LogSeverity }): MonitoringContext => {
  return {
    logger: {
      debug: buildLogMethod('DEBUG', { minimumSeverity: logLevel }),
      error: buildLogMethod('ERROR', { minimumSeverity: logLevel }),
      info: buildLogMethod('INFO', { minimumSeverity: logLevel }),
    },
  };
};
