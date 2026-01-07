import type { SecretDataManagerStorage, SecretDataReference, SecretData } from '@sema4ai/secret-management';
import type { DatabaseClient } from '../database/DatabaseClient.js';

export const createSecretStorage = (database: DatabaseClient): SecretDataManagerStorage => ({
  deleteSecretData: async <ValueType>({ ref }: { ref: SecretDataReference<ValueType> }): Promise<void> => {
    await database.deleteSecretData({ id: ref });
  },

  getSecretData: async <ValueType>({ ref }: { ref: SecretDataReference<ValueType> }): Promise<SecretData | null> => {
    const result = await database.getSecretData({ id: ref });

    if (!result.success || !result.data) {
      return null;
    }

    return {
      id: result.data.id,
      masterKeyId: result.data.master_key_id,
      dataKey: result.data.data_key,
      encryptedSecretValue: result.data.encrypted_secret_value,
    };
  },

  upsertSecretData: async ({ data }: { data: SecretData }): Promise<void> => {
    await database.upsertSecretData({
      secretData: {
        id: data.id,
        master_key_id: data.masterKeyId,
        data_key: JSON.stringify(data.dataKey),
        encrypted_secret_value: JSON.stringify(data.encryptedSecretValue),
      },
    });
  },
});
