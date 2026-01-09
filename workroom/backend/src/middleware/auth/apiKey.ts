import type { NextFunction, Request, Response } from 'express';
import { API_KEY_PREFIX, hashApiKey, type ApiKeysManager } from '../../apiKeys/index.js';
import type { ErrorResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';

type ApiKeyExtractionResult =
  | { success: true; apiKey: string }
  | { success: false; error: 'missing_authorization_header' | 'invalid_auth_type' | 'missing_api_key_prefix' };

const extractApiKeyFromAuthorizationHeader = (authorizationHeader: string | undefined): ApiKeyExtractionResult => {
  if (!authorizationHeader) {
    return { success: false, error: 'missing_authorization_header' };
  }

  const [authType, token] = authorizationHeader.trim().split(/\s+/);

  if (authType.toLowerCase() !== 'bearer') {
    return { success: false, error: 'invalid_auth_type' };
  }

  if (!token || !token.startsWith(`${API_KEY_PREFIX}_`)) {
    return { success: false, error: 'missing_api_key_prefix' };
  }

  return { success: true, apiKey: token };
};

const getErrorMessageForExtractionFailure = (
  error: 'missing_authorization_header' | 'invalid_auth_type' | 'missing_api_key_prefix',
): string => {
  switch (error) {
    case 'missing_authorization_header':
      return 'Missing Authorization header';
    case 'invalid_auth_type':
      return 'Invalid Authorization header: Expected Bearer token';
    case 'missing_api_key_prefix':
      return `Invalid API key format: Expected key starting with "${API_KEY_PREFIX}_"`;
    default:
      error satisfies never;
      return 'Invalid or missing API key';
  }
};

export const createApiKeyAuthMiddleware = ({
  apiKeysManager,
  monitoring,
}: {
  apiKeysManager: ApiKeysManager;
  monitoring: MonitoringContext;
}) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const extractedApiKeyResult = extractApiKeyFromAuthorizationHeader(req.headers.authorization);

    if (!extractedApiKeyResult.success) {
      const errorMessage = getErrorMessageForExtractionFailure(extractedApiKeyResult.error);

      monitoring.logger.info(`API key authentication failed: ${extractedApiKeyResult.error}`, {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res.status(401).json({ error: { code: 'unauthorized', message: errorMessage } } satisfies ErrorResponse);
    }

    const apiKeyHash = hashApiKey(extractedApiKeyResult.apiKey);
    const apiKeyResult = await apiKeysManager.getApiKeyByHash({ hash: apiKeyHash });

    if (!apiKeyResult.success) {
      monitoring.logger.error('API key authentication failed: Database error', {
        errorName: apiKeyResult.error.code,
        errorMessage: apiKeyResult.error.message,
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res
        .status(500)
        .json({ error: { code: 'internal_error', message: 'Internal server error' } } satisfies ErrorResponse);
    }

    if (!apiKeyResult.data) {
      monitoring.logger.info('API key authentication failed: API key not found', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res
        .status(401)
        .json({ error: { code: 'unauthorized', message: 'Invalid API key' } } satisfies ErrorResponse);
    }

    const { id: apiKeyId, name: apiKeyName } = apiKeyResult.data;

    apiKeysManager.setLastUsedAt({ id: apiKeyId }).catch((error) => {
      monitoring.logger.error('Failed to update API key lastUsedAt', {
        apiKeyId,
        error: error as Error,
      });
    });

    res.locals.apiKey = { id: apiKeyId, name: apiKeyName };

    return next();
  };
};
