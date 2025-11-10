import type { Cookie } from 'express-session';
import type { ColumnType, Insertable, JSONColumnType, Selectable, Updateable } from 'kysely';
import type { ResourceTimestampTrait } from './traits.js';
import { type Session as SessionData } from '../../session/payload.js';

export type StoredSession = NonNullable<SessionData> & {
  cookie: Cookie;
};

export type SessionTable = {
  id: string;
  data: JSONColumnType<StoredSession>;
  expires: ColumnType<Date, string, string>;
} & ResourceTimestampTrait;

export type Session = Selectable<SessionTable>;
export type NewSession = Insertable<SessionTable>;
export type SessionUpdate = Updateable<SessionTable>;
