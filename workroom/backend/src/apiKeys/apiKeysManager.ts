import { createHash, randomBytes } from 'crypto';
import type { SecretDataManager } from '@sema4ai/secret-management';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Result } from '../utils/result.js';

const API_KEY_PREFIX = 's4w' as const;

export enum ApiKeyErrorCode {
  ApiKeyNotFound = 'api_key_not_found',
  FailedToEncryptApiKey = 'failed_to_encrypt_api_key',
  FailedToCreateApiKey = 'failed_to_create_api_key',
  FailedToDecryptApiKey = 'failed_to_decrypt_api_key',
  FailedToDeleteApiKey = 'failed_to_delete_api_key',
  FailedToListApiKeys = 'failed_to_list_api_keys',
  FailedToUpdateApiKey = 'failed_to_update_api_key',
}

export type ApiKeyMetadata = {
  createdAt: string;
  id: string;
  lastUsedAt: string | null;
  name: string;
  updatedAt: string;
};

export type ApiKeyWithValue = ApiKeyMetadata & {
  value: string;
};

const generateApiKey = (): string => {
  return `${API_KEY_PREFIX}_${randomBytes(32).toString('hex')}`;
};

const hashApiKey = (apiKey: string): string => {
  return createHash('sha256').update(apiKey).digest('hex');
};

export const createApiKeysManager = ({
  database,
  monitoring,
  secretDataManager,
}: {
  database: DatabaseClient;
  monitoring: MonitoringContext;
  secretDataManager: SecretDataManager;
}) => ({
  createApiKey: async ({
    name,
  }: {
    name: string;
  }): Promise<
    Result<
      ApiKeyWithValue,
      { code: ApiKeyErrorCode.FailedToEncryptApiKey | ApiKeyErrorCode.FailedToCreateApiKey; message: string }
    >
  > => {
    const value = generateApiKey();

    const secretResult = await secretDataManager.createSecretData({ value });
    if (!secretResult.success) {
      monitoring.logger.error('Failed to create secret data for API key', {
        errorMessage: secretResult.error.message,
        errorName: secretResult.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToEncryptApiKey,
          message: `Failed to encrypt API key "${name}"`,
        },
      };
    }

    const secretDataId = secretResult.data;
    const valueHash = hashApiKey(value);

    const insertResult = await database.insertApiKey({
      apiKey: {
        name,
        secret_data_id: secretDataId,
        value_hash: valueHash,
      },
    });

    if (!insertResult.success) {
      monitoring.logger.error('Failed to insert API key', {
        errorMessage: insertResult.error.message,
        errorName: insertResult.error.code,
      });
      const rolledBackSecretCreation = await secretDataManager.deleteSecretData({ ref: secretDataId });

      if (!rolledBackSecretCreation.success) {
        monitoring.logger.error('Failed to delete the secret after a failed API key insertion', {
          errorMessage: rolledBackSecretCreation.error.message,
          errorName: rolledBackSecretCreation.error.code,
        });
      }

      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToCreateApiKey,
          message: `Failed to create API key "${name}"`,
        },
      };
    }

    return {
      success: true,
      data: {
        createdAt: insertResult.data.created_at.toISOString(),
        id: insertResult.data.id,
        lastUsedAt: insertResult.data.last_used_at?.toISOString() ?? null,
        name: insertResult.data.name,
        updatedAt: insertResult.data.updated_at.toISOString(),
        value,
      },
    };
  },

  listApiKeys: async (): Promise<
    Result<Array<ApiKeyMetadata>, { code: ApiKeyErrorCode.FailedToListApiKeys; message: string }>
  > => {
    const result = await database.selectApiKeys();

    if (!result.success) {
      monitoring.logger.error('Failed to list API keys', {
        errorMessage: result.error.message,
        errorName: result.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToListApiKeys,
          message: 'Failed to list API keys',
        },
      };
    }

    return {
      success: true,
      data: result.data.map((key) => ({
        createdAt: key.created_at.toISOString(),
        id: key.id,
        lastUsedAt: key.last_used_at?.toISOString() ?? null,
        name: key.name,
        updatedAt: key.updated_at.toISOString(),
      })),
    };
  },

  getApiKey: async ({
    id,
  }: {
    id: string;
  }): Promise<Result<ApiKeyMetadata | null, { code: ApiKeyErrorCode.ApiKeyNotFound; message: string }>> => {
    const result = await database.selectApiKeyById({ id });

    if (!result.success) {
      monitoring.logger.error('Failed to get API key', {
        apiKeyId: id,
        errorMessage: result.error.message,
        errorName: result.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.ApiKeyNotFound,
          message: `API key (id: "${id}") not found`,
        },
      };
    }

    if (!result.data) {
      return {
        success: true,
        data: null,
      };
    }

    return {
      success: true,
      data: {
        createdAt: result.data.created_at.toISOString(),
        id: result.data.id,
        lastUsedAt: result.data.last_used_at?.toISOString() ?? null,
        name: result.data.name,
        updatedAt: result.data.updated_at.toISOString(),
      },
    };
  },

  previewApiKey: async ({
    id,
  }: {
    id: string;
  }): Promise<
    Result<
      ApiKeyWithValue | null,
      { code: ApiKeyErrorCode.ApiKeyNotFound | ApiKeyErrorCode.FailedToDecryptApiKey; message: string }
    >
  > => {
    const apiKeyResult = await database.selectApiKeyByIdFull({ id });

    if (!apiKeyResult.success) {
      monitoring.logger.error('Failed to get API key for preview', {
        apiKeyId: id,
        errorMessage: apiKeyResult.error.message,
        errorName: apiKeyResult.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.ApiKeyNotFound,
          message: `API key (id: "${id}") not found`,
        },
      };
    }

    if (!apiKeyResult.data) {
      return {
        success: true,
        data: null,
      };
    }

    const secretResult = await secretDataManager.getSecretData(apiKeyResult.data.secret_data_id);

    if (!secretResult.success) {
      monitoring.logger.error('Failed to decrypt API key', {
        apiKeyId: id,
        errorMessage: secretResult.error.message,
        errorName: secretResult.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToDecryptApiKey,
          message: `Failed to decrypt API key (id: "${id}")`,
        },
      };
    }

    return {
      success: true,
      data: {
        createdAt: apiKeyResult.data.created_at.toISOString(),
        id: apiKeyResult.data.id,
        lastUsedAt: apiKeyResult.data.last_used_at?.toISOString() ?? null,
        name: apiKeyResult.data.name,
        updatedAt: apiKeyResult.data.updated_at.toISOString(),
        value: secretResult.data.secretValue,
      },
    };
  },

  updateApiKey: async ({
    id,
    name,
  }: {
    id: string;
    name: string;
  }): Promise<Result<ApiKeyMetadata | null, { code: ApiKeyErrorCode.FailedToUpdateApiKey; message: string }>> => {
    const result = await database.updateApiKey({ id, name });

    if (!result.success) {
      monitoring.logger.error('Failed to update API key', {
        apiKeyId: id,
        errorMessage: result.error.message,
        errorName: result.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToUpdateApiKey,
          message: `Failed to update API key (id: "${id}")`,
        },
      };
    }

    if (!result.data) {
      return {
        success: true,
        data: null,
      };
    }

    return {
      success: true,
      data: {
        createdAt: result.data.created_at.toISOString(),
        id: result.data.id,
        lastUsedAt: result.data.last_used_at?.toISOString() ?? null,
        name: result.data.name,
        updatedAt: result.data.updated_at.toISOString(),
      },
    };
  },

  deleteApiKey: async ({
    id,
  }: {
    id: string;
  }): Promise<Result<{ id: string } | null, { code: ApiKeyErrorCode.FailedToDeleteApiKey; message: string }>> => {
    const deleteResult = await database.deleteApiKey({ id });

    if (!deleteResult.success) {
      monitoring.logger.error('Failed to delete API key', {
        apiKeyId: id,
        errorMessage: deleteResult.error.message,
        errorName: deleteResult.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.FailedToDeleteApiKey,
          message: `Failed to delete API key (id: "${id}")`,
        },
      };
    }

    if (!deleteResult.data) {
      return {
        success: true,
        data: null,
      };
    }

    const secretDeletionResult = await secretDataManager.deleteSecretData({
      ref: deleteResult.data.secret_data_id,
    });

    if (!secretDeletionResult.success) {
      monitoring.logger.error('Failed to delete secret data after API key deletion', {
        apiKeyId: id,
        secretId: deleteResult.data.secret_data_id,
        errorMessage: secretDeletionResult.error.message,
        errorName: secretDeletionResult.error.code,
      });
    }

    return {
      success: true,
      data: { id: deleteResult.data.id },
    };
  },

  getApiKeyByHash: async ({
    hash,
  }: {
    hash: string;
  }): Promise<
    Result<{ id: string; name: string } | null, { code: ApiKeyErrorCode.ApiKeyNotFound; message: string }>
  > => {
    const result = await database.selectApiKeyByHash({ hash });

    if (!result.success) {
      monitoring.logger.error('Failed to get API key by hash', {
        errorMessage: result.error.message,
        errorName: result.error.code,
      });
      return {
        success: false,
        error: {
          code: ApiKeyErrorCode.ApiKeyNotFound,
          message: 'Failed to get API key by hash',
        },
      };
    }

    if (!result.data) {
      return {
        success: true,
        data: null,
      };
    }

    return {
      success: true,
      data: {
        id: result.data.id,
        name: result.data.name,
      },
    };
  },

  setLastUsedAt: async ({ id }: { id: string }): Promise<void> => {
    await database.updateApiKeyLastUsedAt({ id });
  },
});

export type ApiKeysManager = ReturnType<typeof createApiKeysManager>;
