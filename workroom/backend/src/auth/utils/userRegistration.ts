import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/users.js';
import { type Result } from '../../utils/result.js';

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
