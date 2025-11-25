import { sql, type Kysely } from 'kysely';
import { omitProperties, pickProperties, sqlNow } from './helpers.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Database } from './types/index.js';
import type { NewUser, User, UserUpdate } from './types/user.js';
import type { NewUserIdentity, UserIdentity, UserIdentityType, UserIdentityUpdate } from './types/userIdentity.js';
import { asResult, type Result } from '../utils/result.js';
import type { Session, StoredSession } from './types/session.js';

export type UpdateUserPayload = Omit<UserUpdate, 'updated_at'> & { id: NonNullable<UserUpdate['id']> };
export type UpdateUserIdentityPayload = {
  authority: NonNullable<UserIdentityUpdate['authority']>;
  email: UserIdentityUpdate['email'];
  type: NonNullable<UserIdentityUpdate['type']>;
  user_id: NonNullable<UserIdentityUpdate['user_id']>;
  value: NonNullable<UserIdentityUpdate['value']>;
};

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

  async deleteSession({ id }: { id: string }): Promise<Result<void>> {
    return asResult(() =>
      this.database //
        .deleteFrom('session')
        .where('id', '=', id)
        .execute()
        .then(NOOP),
    );
  }

  async findActiveSession({ id }: { id: string }): Promise<Result<Session | null>> {
    return asResult(() =>
      this.database
        .selectFrom('session')
        .selectAll()
        .where('id', '=', id)
        .where('expires', '>=', new Date())
        .executeTakeFirst()
        .then((res) => res ?? null),
    );
  }

  async findActiveSessionsForUser({ userId }: { userId: string }): Promise<Result<Array<{ sessionId: string }>>> {
    return asResult(() =>
      this.database
        .selectFrom('session')
        .select('id')
        .where('expires', '>=', new Date())
        .where(sql`data->'auth'->>'userId'`, '=', userId)
        .execute()
        .then((results) => results.map((result) => ({ sessionId: result.id }))),
    );
  }

  async findUserIdentitiesWithEmail({ email }: { email: string }): Promise<Result<Array<UserIdentity>>> {
    return asResult(() =>
      this.database //
        .selectFrom('user_identity')
        .selectAll()
        .where('email', '=', email)
        .execute(),
    );
  }

  async findUserIdentity({
    authority,
    identityValue,
    type,
  }: {
    authority: string;
    identityValue: string;
    type: UserIdentityType;
  }): Promise<Result<UserIdentity | null>> {
    const result = await asResult(() =>
      this.database
        .selectFrom('user_identity')
        .selectAll()
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
      data: result.data ?? null,
    };
  }

  async findUserIdentities({
    authority,
    identityValues,
    type,
  }: {
    authority: string;
    identityValues: Array<string>;
    type: UserIdentityType;
  }): Promise<Result<Array<UserIdentity>>> {
    return asResult(() =>
      this.database
        .selectFrom('user_identity')
        .selectAll()
        .where('type', '=', type)
        .where('authority', '=', authority)
        .where('value', 'in', identityValues)
        .execute(),
    );
  }

  async getAdminUserIds(): Promise<Result<Array<string>>> {
    return asResult(() =>
      this.database
        .selectFrom('user')
        .select('id')
        .where('role', '=', 'admin')
        .execute()
        .then((results) => results.map((result) => result.id)),
    );
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

  async getUserIds(): Promise<Result<Array<string>>> {
    return asResult(() =>
      this.database
        .selectFrom('user')
        .select('id')
        .execute()
        .then((results) => results.map((result) => result.id)),
    );
  }

  async getUsers(): Promise<Result<Array<User>>> {
    return asResult(() =>
      this.database //
        .selectFrom('user')
        .selectAll()
        .execute(),
    );
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

  async setSession({
    id,
    data,
    expires,
  }: {
    id: string;
    data: StoredSession;
    expires: Date;
  }): Promise<Result<Session>> {
    const dataString = JSON.stringify(data);

    return asResult(() =>
      this.database
        .insertInto('session')
        .values({
          id,
          data: dataString,
          expires: expires.toISOString(),
        })
        .onConflict((oc) =>
          oc.column('id').doUpdateSet({
            data: dataString,
            expires: expires.toISOString(),
            updated_at: sql`NOW()`,
          }),
        )
        .returningAll()
        .executeTakeFirstOrThrow(),
    );
  }

  async setSessionExpiry({ expires, id }: { expires: Date; id: string }): Promise<Result<void>> {
    return asResult(() =>
      this.database
        .updateTable('session')
        .set({
          expires: expires.toISOString(),
          updated_at: sql`NOW()`,
        })
        .where('id', '=', id)
        .execute()
        .then(NOOP),
    );
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

  async updateUserIdentity({ userIdentity }: { userIdentity: UpdateUserIdentityPayload }): Promise<Result<void>> {
    return asResult(() =>
      this.database
        .updateTable('user_identity')
        .set(pickProperties(userIdentity, ['email']))
        .set('updated_at', sqlNow())
        .where((eb) => eb.and(pickProperties(userIdentity, ['user_id', 'authority', 'type', 'value'])))
        .execute()
        .then(NOOP),
    );
  }
}
