import type { TRPC_ERROR_CODE_KEY } from '@trpc/server/rpc';
import { ApiKeyErrorCode } from '../../apiKeys/index.js';

const apiKeyErrorToTRPCCode: Record<ApiKeyErrorCode, TRPC_ERROR_CODE_KEY> = {
  [ApiKeyErrorCode.ApiKeyNotFound]: 'NOT_FOUND',
  [ApiKeyErrorCode.FailedToCreateApiKey]: 'INTERNAL_SERVER_ERROR',
  [ApiKeyErrorCode.FailedToDecryptApiKey]: 'INTERNAL_SERVER_ERROR',
  [ApiKeyErrorCode.FailedToDeleteApiKey]: 'INTERNAL_SERVER_ERROR',
  [ApiKeyErrorCode.FailedToEncryptApiKey]: 'INTERNAL_SERVER_ERROR',
  [ApiKeyErrorCode.FailedToListApiKeys]: 'INTERNAL_SERVER_ERROR',
  [ApiKeyErrorCode.FailedToUpdateApiKey]: 'INTERNAL_SERVER_ERROR',
};

export const toTRPCError = (error: {
  code: ApiKeyErrorCode;
  message: string;
}): { code: TRPC_ERROR_CODE_KEY; message: string } => ({
  code: apiKeyErrorToTRPCCode[error.code],
  message: error.message,
});

export const notAvailableForConfiguration = ({
  feature,
}: {
  feature: 'API keys management' | 'User management';
}): { code: TRPC_ERROR_CODE_KEY; message: string } => ({
  code: 'NOT_IMPLEMENTED',
  message: `${feature} is not configured`,
});
