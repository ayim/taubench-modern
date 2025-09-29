import { S3 } from '@aws-sdk/client-s3';
import { AssumeRoleCommand, STSClient } from '@aws-sdk/client-sts';
import type { Result } from '../../utils/result.js';

type RoleBasedS3ClientResultErrorCode = 'failed_to_assume_role' | 'invalid_aws_credentials_received';

export type RoleBasedS3ClientResult = Result<
  { s3: S3 },
  {
    message: string;
    code: RoleBasedS3ClientResultErrorCode;
  }
>;

const DEFAULT_AWS_MAX_RETRIES = 3;

export const getRoleBasedS3Client = async ({
  awsRegion,
  awsRoleARN,
}: {
  awsRegion: string;
  awsRoleARN: string;
}): Promise<RoleBasedS3ClientResult> => {
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
      const command = new AssumeRoleCommand({
        RoleSessionName: 'spar-aws-file-mgmt',
        RoleArn: awsRoleARN,
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

      return {
        success: true,
        data: {
          Credentials: {
            AccessKeyId: response.Credentials.AccessKeyId,
            SecretAccessKey: response.Credentials.SecretAccessKey,
            SessionToken: response.Credentials.SessionToken,
          },
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
    data: {
      s3: new S3({
        region: awsRegion,
        maxAttempts: DEFAULT_AWS_MAX_RETRIES,
        credentials: {
          accessKeyId: Credentials.AccessKeyId,
          secretAccessKey: Credentials.SecretAccessKey,
          sessionToken: Credentials.SessionToken,
        },
      }),
    },
  };
};
