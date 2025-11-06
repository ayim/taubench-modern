import type { Kysely } from 'kysely';
import { omitProperties, sqlNow } from './helpers.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { NewUserIdentity, UserIdentityTable, UserIdentityType } from './types/userIdentities.js';
import type { NewUser, User, UserTable, UserUpdate } from './types/users.js';
import { asResult, type Result } from '../utils/result.js';

export interface Database {
  user: UserTable;
  user_identity: UserIdentityTable;
}

export type UpdateUserPayload = Omit<UserUpdate, 'updated_at'> & { id: NonNullable<UserUpdate['id']> };

const NOOP = () => {};

export class DatabaseClient {
  private database: Kysely<Database>;
  private monitoring: MonitoringContext;

  constructor({ database, monitoring }: { database: Kysely<Database>; monitoring: MonitoringContext }) {
    this.database = database;
    this.monitoring = monitoring;
  }

  async checkLiveness(): Promise<Result<void>> {
    return asResult(() =>
      this.database
        .selectNoFrom((eb) => eb.val(1).as('test'))
        .executeTakeFirstOrThrow()
        .then(NOOP),
    );
  }

  async createUser({ user }: { user: NewUser }): Promise<Result<void>> {
    return asResult(() =>
      this.database //
        .insertInto('user')
        .values(user)
        .execute()
        .then(NOOP),
    );
  }

  async createUserIdentity({ userIdentity }: { userIdentity: NewUserIdentity }): Promise<Result<void>> {
    return asResult(() =>
      this.database //
        .insertInto('user_identity')
        .values(userIdentity)
        .execute()
        .then(NOOP),
    );
  }

  async findUserIdForIdentity({
    authority,
    identityValue,
    type,
  }: {
    authority: string;
    identityValue: string;
    type: UserIdentityType;
  }): Promise<Result<string | null>> {
    const result = await asResult(() =>
      this.database
        .selectFrom('user_identity')
        .select('user_id')
        .where('type', '=', type)
        .where('authority', '=', authority)
        .where('value', '=', identityValue)
        .executeTakeFirst(),
    );
    if (!result.success) {
      return result;
    }

    return {
      success: true,
      data: result.data?.user_id ?? null,
    };
  }

  async getUser({ id }: { id: string }): Promise<Result<User>> {
    return asResult(() =>
      this.database //
        .selectFrom('user')
        .selectAll()
        .where('id', '=', id)
        .executeTakeFirstOrThrow(),
    );
  }

  async getUsers(): Promise<Result<Array<User>>> {
    return asResult(() => this.database.selectFrom('user').selectAll().execute());
  }

  async getUsersCount(): Promise<Result<number>> {
    const userCountResult = await asResult(() =>
      this.database
        .selectFrom('user')
        .select((qb) => qb.fn.countAll().as('count'))
        .executeTakeFirstOrThrow(),
    );

    if (!userCountResult.success) {
      return userCountResult;
    }

    const count = Number(userCountResult.data?.count);
    if (isNaN(count)) {
      this.monitoring.logger.error('Invalid users count', {
        errorMessage: `Count was not a number: ${userCountResult.data?.count}`,
      });

      return {
        success: false,
        error: {
          code: 'invalid_db_count_result',
          message: 'Failed counting user results: Query returned invalid count',
        },
      };
    }

    return {
      success: true,
      data: count,
    };
  }

  async updateUser({ user }: { user: UpdateUserPayload }): Promise<Result<void>> {
    return asResult(() =>
      this.database
        .updateTable('user')
        .set(omitProperties(user, ['id']))
        .set('updated_at', sqlNow())
        .where('id', '=', user.id)
        .execute()
        .then(NOOP),
    );
  }
}
