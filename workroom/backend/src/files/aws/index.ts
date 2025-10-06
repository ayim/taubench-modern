import { join } from 'node:path';
import type { Readable } from 'node:stream';
import { DeleteObjectCommand, GetObjectCommand, type S3 } from '@aws-sdk/client-s3';
import { createPresignedPost, type PresignedPostOptions } from '@aws-sdk/s3-presigned-post';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { MonitoringContext } from '../../monitoring/index.js';
import { asResult, type Result } from '../../utils/result.js';
import type {
  CreateFileOptions,
  File,
  FilesManager,
  GetFileOptions,
  PresignedGet,
  PresignedPost,
} from '../filesManagement.js';
import { getRoleBasedS3Client } from './s3Client.js';
import { getContentType } from '../utils.js';

export interface AWSFilesStorageTarget {
  bucketName: string;
  region: string;
  roleArn: string;
}

const createDeleteFile =
  ({ monitoring, s3BucketName, s3Client }: { monitoring: MonitoringContext; s3BucketName: string; s3Client: S3 }) =>
  async (file: File): Promise<Result<{ deleted: true }>> => {
    const key = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Delete S3 file', {
      fileName: key,
      objectStorageBucketName: s3BucketName,
    });

    const command = new DeleteObjectCommand({
      Bucket: s3BucketName,
      Key: key,
    });

    const result = await asResult(() => s3Client.send(command));
    if (!result.success) {
      monitoring.logger.error('Failed deleting S3 file', {
        errorName: result.error.code,
        errorMessage: result.error.message,
        fileName: key,
        objectStorageBucketName: s3BucketName,
      });

      return result;
    }

    return {
      success: true,
      data: { deleted: true },
    };
  };

const createGetFileStream =
  ({ monitoring, s3BucketName, s3Client }: { monitoring: MonitoringContext; s3BucketName: string; s3Client: S3 }) =>
  async (file: File): Promise<Result<{ fileStream: Readable }>> => {
    const key = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Get S3 file stream', {
      fileName: key,
      objectStorageBucketName: s3BucketName,
    });

    const command = new GetObjectCommand({
      Bucket: s3BucketName,
      Key: key,
    });

    try {
      const response = await s3Client.send(command);
      if (!response.Body) {
        throw new Error('Unexpected: response for GetObjectCommand does not have a body');
      }

      const fileStream = response.Body as Readable;

      return {
        success: true,
        data: { fileStream },
      };
    } catch (unknownError) {
      const error = unknownError as Error;

      monitoring.logger.info('Failed getting S3 file stream', {
        error,
        fileName: key,
        objectStorageBucketName: s3BucketName,
      });

      if (error.name === 'NoSuchKey') {
        return {
          success: false,
          error: {
            code: 'not_found',
            message: `Cannot find file ${key}`,
          },
        };
      }

      return {
        success: false,
        error: {
          code: 'unexpected_get_file_stream_error',
          message: `Failed fetching file stream: ${error.message}`,
        },
      };
    }
  };

const createGetGetSignedUrl =
  ({ monitoring, s3BucketName, s3Client }: { monitoring: MonitoringContext; s3BucketName: string; s3Client: S3 }) =>
  async (file: GetFileOptions): Promise<Result<PresignedGet>> => {
    const { baseFolder, contentDispositionType, expiresIn, fileId, fileName } = file;

    const key = join(baseFolder, fileId);

    monitoring.logger.info('Get GET signed URL', {
      contentDispositionType,
      expiresInMin: expiresIn,
      fileId,
      fileName: key,
      objectStorageBucketName: s3BucketName,
    });

    const command = (() => {
      switch (contentDispositionType) {
        case 'attachment': {
          return new GetObjectCommand({
            Bucket: s3BucketName,
            Key: key,
            ResponseContentDisposition: `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
          });
        }
        case 'inline': {
          return new GetObjectCommand({
            Bucket: s3BucketName,
            Key: key,
            ResponseContentType: getContentType({ fileName }),
            ResponseContentDisposition: `inline; filename*=UTF-8''${encodeURIComponent(fileName)}`,
          });
        }
        default:
          exhaustiveCheck(contentDispositionType);
      }
    })();

    const urlResult = await asResult(() => getSignedUrl(s3Client, command, { expiresIn }));
    if (!urlResult.success) {
      monitoring.logger.error('Failed generating signed GET url', {
        errorName: urlResult.error.code,
        errorMessage: urlResult.error.message,
        expiresInMin: expiresIn,
        fileId,
        fileName: key,
        objectStorageBucketName: s3BucketName,
      });

      return urlResult;
    }

    return {
      success: true,
      data: { url: urlResult.data },
    };
  };

const createGetPostSignedUrl =
  ({ monitoring, s3BucketName, s3Client }: { monitoring: MonitoringContext; s3BucketName: string; s3Client: S3 }) =>
  async (file: CreateFileOptions): Promise<Result<PresignedPost>> => {
    const key = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Get POST signed URL', {
      fileName: key,
      objectStorageBucketName: s3BucketName,
    });

    const options: PresignedPostOptions = {
      Bucket: s3BucketName,
      Key: key,
      Expires: file.expiresIn,
      Fields: {
        key: key,
      },
      Conditions: file.fileSize !== undefined ? [['content-length-range', file.fileSize, file.fileSize]] : undefined,
    };

    const urlResult = await asResult(() => createPresignedPost(s3Client, options));
    if (!urlResult.success) {
      monitoring.logger.error('Failed generating signed POST url', {
        errorName: urlResult.error.code,
        errorMessage: urlResult.error.message,
        fileName: key,
        objectStorageBucketName: s3BucketName,
      });

      return urlResult;
    }

    return {
      success: true,
      data: {
        fields: urlResult.data.fields,
        headers: {},
        method: 'POST',
        url: urlResult.data.url,
      },
    };
  };

export const createAWSFilesManager = async ({
  aws,
  monitoring,
}: {
  aws: AWSFilesStorageTarget;
  monitoring: MonitoringContext;
}): Promise<FilesManager> => {
  const s3ClientResult = await getRoleBasedS3Client({
    awsRegion: aws.region,
    awsRoleARN: aws.roleArn,
  });
  if (!s3ClientResult.success) {
    throw new Error(`Failed configuring AWS files manager S3 client: ${s3ClientResult.error.message}`);
  }

  const s3Client = s3ClientResult.data.s3;

  return {
    deleteFile: createDeleteFile({ monitoring, s3BucketName: aws.bucketName, s3Client }),
    getFileStream: createGetFileStream({ monitoring, s3BucketName: aws.bucketName, s3Client }),
    getGetSignedUrl: createGetGetSignedUrl({ monitoring, s3BucketName: aws.bucketName, s3Client }),
    getPostSignedUrl: createGetPostSignedUrl({ monitoring, s3BucketName: aws.bucketName, s3Client }),
  };
};
