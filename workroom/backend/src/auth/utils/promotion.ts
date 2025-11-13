import { extractEmailFromClaims } from './oidcUserRegistration.js';
import type { Configuration } from '../../configuration.js';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { OIDCTokenClaims } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { SessionManager } from '../../session/SessionManager.js';
import { destroySessionsForUser } from '../../session/utils.js';

/**
 * Check to see if users with configured email addresses can be
 * auto promoted to admin users at application startup. This
 * function will destroy user sessions, if found, to ensure that
 * any logged-in user being promoted gets a clean session.
 */
export const autoPromoteUsersWithEmailsToAdmin = async ({
  database,
  emails,
  monitoring,
  sessionManager,
}: {
  database: DatabaseClient;
  emails: Array<string>;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
}): Promise<void> => {
  if (emails.length === 0) return;

  monitoring.logger.info('Auto-promotion process started', {
    count: emails.length,
  });

  const adminUserIdsResult = await database.getAdminUserIds();
  if (!adminUserIdsResult.success) {
    throw new Error(`Failed fetching admin user IDs: ${adminUserIdsResult.error.message}`);
  }
  const existingAdminUserIds = adminUserIdsResult.data;

  await Promise.all(
    emails.map(async (email) => {
      const identityResult = await database.findUserIdentitiesWithEmail({ email });
      if (!identityResult.success) {
        throw new Error(`Failed retrieving user identities for email: ${identityResult.error.message}`);
      }

      const identities = identityResult.data;

      monitoring.logger.debug('Attempting to promote identities for email', {
        count: identities.length,
        emailAddress: email,
      });

      const userIds = [...new Set(identities.map((identity) => identity.user_id))]
        // Filter out IDs that are already flagged as being administrator user IDs
        .filter((userId) => existingAdminUserIds.includes(userId) === false);
      if (userIds.length === 0) return;

      for (const userId of userIds) {
        monitoring.logger.info('Auto promoting user to admin', {
          userId,
        });

        const updateUserResult = await database.updateUser({
          user: {
            id: userId,
            role: 'admin',
          },
        });
        if (!updateUserResult.success) {
          throw new Error(`Failed auto promoting user: ${updateUserResult.error.message}`);
        }

        const destroyResult = await destroySessionsForUser({
          database,
          monitoring,
          sessionManager,
          userId,
        });
        if (!destroyResult.success) {
          throw new Error(`Failed auto promoting user: Failed clearing user sessions: ${destroyResult.error.message}`);
        }
      }
    }),
  );

  monitoring.logger.info('Auto-promotion process completed', {
    count: emails.length,
  });
};

/**
 * Check to see if an OIDC-authenticated user can be automatically
 * promoted to an admin user. Done in flight during login, so session
 * clearing isn't used here.
 */
export const checkOIDCUserForAutoPromotion = async ({
  configuration,
  database,
  monitoring,
  oidcTokenClaims,
  userId,
}: {
  configuration: Configuration;
  database: DatabaseClient;
  monitoring: MonitoringContext;
  oidcTokenClaims: OIDCTokenClaims;
  userId: string;
}): Promise<UserRole | null> => {
  const userEmail = extractEmailFromClaims(oidcTokenClaims);

  if (userEmail !== null && configuration.auth.autoPromoteEmails.includes(userEmail)) {
    monitoring.logger.info('Auto promoting OIDC user', {
      userId,
      userRole: 'admin',
    });

    // Promote single user
    const updateUserResult = await database.updateUser({
      user: {
        id: userId,
        role: 'admin',
      },
    });
    if (!updateUserResult.success) {
      throw new Error(`Failed auto promoting user: ${updateUserResult.error.message}`);
    }

    return 'admin';
  }

  return null;
};
