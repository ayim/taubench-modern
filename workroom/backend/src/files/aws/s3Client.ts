import { S3 } from '@aws-sdk/client-s3';
import { AssumeRoleCommand, STSClient } from '@aws-sdk/client-sts';
import type { Result } from '@sema4ai/shared-utils';
import type { MonitoringContext } from '../../monitoring/index.js';

type RoleBasedS3ClientResultErrorCode = 'failed_to_assume_role' | 'invalid_aws_credentials_received';

export type S3ClientFactory = {
  getS3Client: () => Promise<
    Result<
      S3,
      {
        message: string;
        code: RoleBasedS3ClientResultErrorCode;
      }
    >
  >;
};

const DEFAULT_AWS_MAX_RETRIES = 3;

export const ROLE_ASSUME_DURATION_IN_SECONDS = 900 as const;
export const CACHED_CREDENTIALS_BUFFER_IN_SECONDS = 60 as const;

type CachedCredentials = {
  assumedAtMs: number;
  credentials: {
    AccessKeyId: string;
    SecretAccessKey: string;
    SessionToken: string;
  };
};

export const getCachedCredentials = ({
  cachedCredentials,
  roleAssumeDurationInSeconds,
  bufferTimeInSeconds,
}: {
  cachedCredentials: CachedCredentials | null;
  roleAssumeDurationInSeconds: number;
  bufferTimeInSeconds: number;
}): CachedCredentials | null => {
  if (!cachedCredentials) {
    return null;
  }

  const expiresAtMs = cachedCredentials.assumedAtMs + roleAssumeDurationInSeconds * 1000;
  const cutoffMs = expiresAtMs - bufferTimeInSeconds * 1000;

  const hasValidCredentials = Date.now() < cutoffMs;

  return hasValidCredentials ? cachedCredentials : null;
};

export const getRoleBasedS3Factory = async ({
  awsRegion,
  awsRoleARN,
  monitoring,
}: {
  awsRegion: string;
  awsRoleARN: string;
  monitoring: MonitoringContext;
}): Promise<S3ClientFactory> => {
  let CACHED_CREDENTIALS: CachedCredentials | null = null;

  return {
    getS3Client: async (): ReturnType<S3ClientFactory['getS3Client']> => {
      const stsClient = new STSClient({ region: awsRegion });

      const assumedRole = await (async (): Promise<
        Result<
          { Credentials: { AccessKeyId: string; SecretAccessKey: string; SessionToken: string } },
          {
            message: string;
            code: RoleBasedS3ClientResultErrorCode;
          }
        >
      > => {
        try {
          const cachedCredentials = getCachedCredentials({
            cachedCredentials: CACHED_CREDENTIALS,
            roleAssumeDurationInSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
            bufferTimeInSeconds: CACHED_CREDENTIALS_BUFFER_IN_SECONDS,
          });

          if (cachedCredentials) {
            monitoring.logger.info(
              `Returning cached assumed role credentials (assumedAtMs: ${cachedCredentials.assumedAtMs})`,
            );
            return {
              success: true,
              data: {
                Credentials: cachedCredentials.credentials,
              },
            };
          }

          const command = new AssumeRoleCommand({
            RoleSessionName: 'spar-aws-file-mgmt',
            RoleArn: awsRoleARN,
            DurationSeconds: ROLE_ASSUME_DURATION_IN_SECONDS,
          });

          const response = await stsClient.send(command);
          if (
            !response.Credentials?.AccessKeyId ||
            !response.Credentials?.SecretAccessKey ||
            !response.Credentials?.SessionToken
          ) {
            return {
              success: false,
              error: {
                message: `Unexpected AWS credentials received while assuming role: ${awsRoleARN}`,
                code: 'invalid_aws_credentials_received',
              },
            };
          }

          const credentials = {
            AccessKeyId: response.Credentials.AccessKeyId,
            SecretAccessKey: response.Credentials.SecretAccessKey,
            SessionToken: response.Credentials.SessionToken,
          };

          const now = Date.now();

          CACHED_CREDENTIALS = {
            assumedAtMs: now,
            credentials,
          };

          return {
            success: true,
            data: {
              Credentials: CACHED_CREDENTIALS.credentials,
            },
          };
        } catch (e) {
          const error = e as Error;

          return {
            success: false,
            error: {
              message: `${error.name}:${error.message}`,
              code: 'failed_to_assume_role',
            },
          };
        }
      })();

      if (!assumedRole.success) {
        return assumedRole;
      }

      const { Credentials } = assumedRole.data;

      return {
        success: true,
        data: new S3({
          region: awsRegion,
          maxAttempts: DEFAULT_AWS_MAX_RETRIES,
          credentials: {
            accessKeyId: Credentials.AccessKeyId,
            secretAccessKey: Credentials.SecretAccessKey,
            sessionToken: Credentials.SessionToken,
          },
        }),
      };
    },
  };
};
