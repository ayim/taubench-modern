import type { Configuration } from '../configuration.js';

type LogMethod = (text: string, data?: Partial<LogAttributes>) => void;
type LogSeverity = 'INFO' | 'ERROR';

export interface LogAttributes {
  authMode: Configuration['auth']['type'];
  authSkip: boolean;
  count: number;
  deploymentType: 'spar';
  error?: Error;
  errorCause: string;
  errorMessage: string;
  errorName: string;
  errorStack: string;
  fileName: string;
  oidcIssuer: string;
  oidcRedirectUrl: string;
  sessionId: string;
  status: number;
  statusText: string;
  port: number;
  processSignal: string;
  requestMethod: string;
  requestUrl: string;
  tenantId: string;
}

export interface LoggingContext {
  error: LogMethod;
  info: LogMethod;
}

export interface MonitoringContext {
  logger: LoggingContext;
}

const buildLogMethod = (severity: LogSeverity): LogMethod => {
  return (text: string, data: Partial<LogAttributes> = {}) => {
    const attributes: Partial<LogAttributes> = { ...data };

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

export const createMonitoringContext = (): MonitoringContext => {
  return {
    logger: {
      error: buildLogMethod('ERROR'),
      info: buildLogMethod('INFO'),
    },
  };
};
