import { Store, type SessionData } from 'express-session';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { StoredSession } from '../database/types/session.js';

export class DatabaseSessionStore extends Store {
  private database: DatabaseClient;
  private sessionExpirySeconds: number;

  constructor({ database, sessionExpirySeconds }: { database: DatabaseClient; sessionExpirySeconds: number }) {
    super();

    this.database = database;
    this.sessionExpirySeconds = sessionExpirySeconds;
  }

  destroy(sid: string, callback?: (err?: unknown) => void): void {
    this.database.deleteSession({ id: sid }).then((deleteResult) => {
      if (!deleteResult.success) {
        callback?.(new Error(`Failed deleting session from database: ${deleteResult.error.message}`));
        return;
      }

      callback?.();
    });
  }

  get(sid: string, callback: (err: unknown, session?: SessionData | null) => void): void {
    this.database.findActiveSession({ id: sid }).then((sessionResult) => {
      if (!sessionResult.success) {
        callback(new Error(`Failed retrieving session from database: ${sessionResult.error.message}`));
        return;
      }

      if (!sessionResult.data) {
        callback(null, null);
        return;
      }

      const sessionData = sessionResult.data.data;
      callback(null, sessionData);
    });
  }

  set(sid: string, session: SessionData, callback?: (err?: unknown) => void): void {
    const expiry = new Date(this.getExpiryTimeInSeconds(session) * 1000);

    this.database
      .setSession({
        id: sid,
        data: session as StoredSession,
        expires: expiry,
      })
      .then((setResult) => {
        if (!setResult.success) {
          callback?.(new Error(`Failed setting session in database: ${setResult.error.message}`));
          return;
        }

        callback?.();
      });
  }

  touch(sid: string, session: SessionData, callback?: (err?: unknown) => void): void {
    const expiry = new Date(this.getExpiryTimeInSeconds(session) * 1000);

    this.database.setSessionExpiry({ expires: expiry, id: sid }).then((updateResult) => {
      if (!updateResult.success) {
        callback?.(new Error(`Failed touching session in database: ${updateResult.error.message}`));
        return;
      }

      callback?.();
    });
  }

  private getExpiryTimeInSeconds(session: SessionData) {
    if (session && session.cookie && session.cookie['expires']) {
      const expireDate = new Date(session.cookie['expires']);
      return Math.ceil(expireDate.valueOf() / 1000);
    }

    return Math.ceil(Date.now() / 1000 + this.sessionExpirySeconds);
  }
}
