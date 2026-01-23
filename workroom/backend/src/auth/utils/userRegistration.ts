import type { Result } from '@sema4ai/shared-utils';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';

export const getNextUserRole = async ({ database }: { database: DatabaseClient }): Promise<Result<UserRole>> => {
  const userCountResult = await database.getUsersCount();
  if (!userCountResult.success) {
    return userCountResult;
  }

  const role: UserRole = userCountResult.data === 0 ? 'admin' : 'knowledgeWorker';

  return {
    success: true,
    data: role,
  };
};
