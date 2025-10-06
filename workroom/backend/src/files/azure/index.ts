import { join } from 'node:path';
import { Readable } from 'node:stream';
import type { ReadableStream } from 'node:stream/web';
import {
  BlobSASPermissions,
  BlobServiceClient,
  generateBlobSASQueryParameters,
  type ContainerClient,
} from '@azure/storage-blob';
import type { MonitoringContext } from '../../monitoring/index.js';
import type {
  CreateFileOptions,
  File,
  FilesManager,
  GetFileOptions,
  PresignedGet,
  PresignedPost,
} from '../filesManagement.js';
import { getImplicitlyAuthenticatedClients } from './containerClient.js';
import type { Result } from '../../utils/result.js';
import { safeParseUrl } from '../../utils/url.js';

export interface AzureFilesStorageTarget {
  clientId: string;
  container: string;
  endpoint: string;
}

const createDeleteFile =
  ({ containerClient, monitoring }: { containerClient: ContainerClient; monitoring: MonitoringContext }) =>
  async (file: File): Promise<Result<{ deleted: true }>> => {
    const key = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Delete blob file', {
      fileName: key,
      objectStorageBucketName: containerClient.containerName,
    });

    try {
      const blobClient = containerClient.getBlobClient(key);
      await blobClient.getProperties();
      await blobClient.delete();

      return { success: true, data: { deleted: true } };
    } catch (err) {
      const error = err as Error & { code?: string };

      monitoring.logger.error('Failed deleting blob', {
        error,
        fileName: key,
        objectStorageBucketName: containerClient.containerName,
      });

      return {
        success: false,
        error:
          error.code === 'BlobNotFound'
            ? {
                code: 'not_found',
                message: `Blob not found when attempting to delete key: ${key}`,
              }
            : {
                code: 'failed_deleting_blob',
                message: `Failed to delete blob at key: ${key}`,
              },
      };
    }
  };

const createGetFileStream =
  ({ containerClient, monitoring }: { containerClient: ContainerClient; monitoring: MonitoringContext }) =>
  async (file: File): Promise<Result<{ fileStream: Readable }>> => {
    const fileIdKey = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Get blob file stream', {
      fileName: fileIdKey,
      objectStorageBucketName: containerClient.containerName,
    });

    try {
      const blobClient = containerClient.getBlobClient(fileIdKey);

      const downloadResponse = await blobClient.download();
      if (!downloadResponse.readableStreamBody) {
        throw new Error('Failed to retrieve blob file stream: No stream body returned in response');
      }

      const readable = (() => {
        if (downloadResponse.readableStreamBody instanceof Readable) {
          return downloadResponse.readableStreamBody;
        } else {
          return Readable.fromWeb(downloadResponse.readableStreamBody as unknown as ReadableStream);
        }
      })();

      return {
        success: true,
        data: {
          fileStream: readable,
        },
      };
    } catch (err) {
      const error = err as Error & { code?: string };

      monitoring.logger.error('Failed retrieving blob stream', {
        error,
        fileName: fileIdKey,
        objectStorageBucketName: containerClient.containerName,
      });

      return {
        success: false,
        error: {
          code: 'download_error',
          message: `Failed retrieving blob download stream: ${fileIdKey}`,
        },
      };
    }
  };

const createGetGetSignedUrl =
  ({
    blobServiceClient,
    containerClient,
    monitoring,
  }: {
    blobServiceClient: BlobServiceClient;
    containerClient: ContainerClient;
    monitoring: MonitoringContext;
  }) =>
  async (file: GetFileOptions): Promise<Result<PresignedGet>> => {
    const fileIdKey = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Get blob GET URL', {
      fileName: fileIdKey,
      objectStorageBucketName: containerClient.containerName,
    });

    try {
      const blobClient = containerClient.getBlobClient(fileIdKey);

      const now = Date.now();
      const startsOn = new Date(now);
      const expiresOn = new Date(now + file.expiresIn * 1000);

      const userDelegationKey = await blobServiceClient.getUserDelegationKey(startsOn, expiresOn);

      const sasToken = generateBlobSASQueryParameters(
        {
          containerName: containerClient.containerName,
          blobName: fileIdKey,
          permissions: BlobSASPermissions.from({ read: true }),
          startsOn,
          expiresOn,
        },
        userDelegationKey,
        blobServiceClient.accountName,
      );

      const urlResult = safeParseUrl(`${blobClient.url}?${sasToken}`);
      if (!urlResult.success) {
        return {
          success: false,
          error: {
            code: 'invalid_get_presigned_url',
            message: urlResult.error.message,
          },
        };
      }

      return {
        success: true,
        data: {
          url: urlResult.data.toString(),
        },
      };
    } catch (err) {
      const error = err as Error;

      monitoring.logger.error('Failed generating blob presigned GET URL', {
        error,
        fileName: fileIdKey,
        objectStorageBucketName: containerClient.containerName,
      });

      return {
        success: false,
        error: {
          code: 'failed_generating_presigned_get_url',
          message: `Failed generating presigned GET URL for blob: ${fileIdKey}`,
        },
      };
    }
  };

const createGetPostSignedUrl =
  ({
    blobServiceClient,
    containerClient,
    monitoring,
  }: {
    blobServiceClient: BlobServiceClient;
    containerClient: ContainerClient;
    monitoring: MonitoringContext;
  }) =>
  async (file: CreateFileOptions): Promise<Result<PresignedPost>> => {
    const fileIdKey = join(file.baseFolder, file.fileId);

    monitoring.logger.info('Get blob POST URL', {
      fileName: fileIdKey,
      objectStorageBucketName: containerClient.containerName,
    });

    try {
      const blobClient = containerClient.getBlobClient(fileIdKey);

      const now = Date.now();
      const startsOn = new Date(now);
      const expiresOn = new Date(now + file.expiresIn * 1000);

      const userDelegationKey = await blobServiceClient.getUserDelegationKey(startsOn, expiresOn);

      const sasToken = generateBlobSASQueryParameters(
        {
          containerName: containerClient.containerName,
          blobName: fileIdKey,
          permissions: BlobSASPermissions.from({ write: true, create: true }),
          startsOn,
          expiresOn,
        },
        userDelegationKey,
        blobServiceClient.accountName,
      );

      const urlResult = safeParseUrl(`${blobClient.url}?${sasToken}`);
      if (!urlResult.success) {
        return {
          success: false,
          error: {
            code: 'invalid_get_presigned_url',
            message: urlResult.error.message,
          },
        };
      }

      return {
        success: true,
        data: {
          fields: {},
          headers: {
            'x-ms-blob-type': 'BlockBlob',
          },
          method: 'PUT',
          url: urlResult.data.toString(),
        },
      };
    } catch (err) {
      const error = err as Error;

      monitoring.logger.error('Failed generating blob presigned POST URL', {
        error,
        fileName: fileIdKey,
        objectStorageBucketName: containerClient.containerName,
      });

      return {
        success: false,
        error: {
          code: 'failed_generating_presigned_post_url',
          message: `Failed generating presigned POST URL for blob: ${fileIdKey}`,
        },
      };
    }
  };

export const createAzureFilesManager = async ({
  azure,
  monitoring,
}: {
  azure: AzureFilesStorageTarget;
  monitoring: MonitoringContext;
}): Promise<FilesManager> => {
  const clientsResult = await getImplicitlyAuthenticatedClients({
    clientId: azure.clientId,
    container: azure.container,
    endpoint: azure.endpoint,
  });
  if (!clientsResult.success) {
    throw new Error(`Failed configuring Azure files manager clients: ${clientsResult.error.message}`);
  }

  const { blobServiceClient, containerClient } = clientsResult.data;

  return {
    deleteFile: createDeleteFile({ containerClient, monitoring }),
    getFileStream: createGetFileStream({ containerClient, monitoring }),
    getGetSignedUrl: createGetGetSignedUrl({ blobServiceClient, containerClient, monitoring }),
    getPostSignedUrl: createGetPostSignedUrl({ blobServiceClient, containerClient, monitoring }),
  };
};
