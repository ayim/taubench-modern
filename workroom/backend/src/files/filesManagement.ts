import type { Readable } from 'node:stream';
import { exhaustiveCheck } from '@sema4ai/shared-utils';
import type { Configuration } from '../configuration.js';
import type { MonitoringContext } from '../monitoring/index.js';
import type { Result } from '../utils/result.js';
import { createAWSFilesManager } from './aws/index.js';
import { createAzureFilesManager } from './azure/index.js';

export interface CreateFileOptions {
  baseFolder: string;
  fileId: string;
  /**
   * Expiry time in seconds
   */
  expiresIn: number;
  /**
   * File size in bytes
   */
  fileSize?: number;
  fileType?: string;
}

export interface File {
  baseFolder: string;
  fileId: string;
  size?: number;
}

export interface GetFileOptions {
  baseFolder: string;
  fileName: string;
  fileId: string;
  /**
   * Expiry time in seconds
   */
  expiresIn: number;
  contentDispositionType: 'inline' | 'attachment';
}

export interface ListFilesOptions {
  baseFolder?: string;
}

export interface PresignedPost {
  fields: Record<string, string>;
  headers: Record<string, string>;
  method: 'POST' | 'PUT';
  url: string;
}

export interface PresignedGet {
  url: string;
}

export interface FilesManager {
  deleteFile(file: File): Promise<Result<{ deleted: true }>>;
  getFileStream(file: File): Promise<Result<{ fileStream: Readable }>>;
  getGetSignedUrl(file: GetFileOptions): Promise<Result<PresignedGet>>;
  getPostSignedUrl(file: CreateFileOptions): Promise<Result<PresignedPost>>;
}

export const createFilesManager = async ({
  configuration,
  monitoring,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
}): Promise<FilesManager> => {
  switch (configuration.files.mode) {
    case 'aws':
      return createAWSFilesManager({
        aws: {
          bucketName: configuration.files.s3BucketName,
          region: configuration.files.awsRegion,
          roleArn: configuration.files.awsRoleArn,
        },
        monitoring,
      });

    case 'azure':
      return createAzureFilesManager({
        azure: {
          clientId: configuration.files.clientId,
          container: configuration.files.containerName,
          endpoint: `https://${configuration.files.storageAccountName}.blob.core.windows.net`,
        },
        monitoring,
      });

    case 'disabled':
      throw new Error(`Files management not supported in this mode: ${configuration.files.mode}`);

    default:
      exhaustiveCheck(configuration.files);
  }
};
