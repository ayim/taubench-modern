import express, { type Router } from 'express';
import createRouter from 'express-promise-router';
import type { Configuration } from '../configuration.js';
import type { FilesManager } from '../files/filesManagement.js';
import { DeleteFileBody, GetDownloadUrlQuery, GetPostSignedUrlBody } from '../files/schemas.js';
import type { ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { formatZodError } from '../utils/error.js';

const createDeleteFile =
  ({
    configuration,
    filesManager,
    monitoring,
  }: {
    configuration: Configuration;
    filesManager: FilesManager;
    monitoring: MonitoringContext;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
    const bodyResult = DeleteFileBody.safeParse(req.body);
    if (!bodyResult.success) {
      monitoring.logger.error('Invalid body received for delete file request', {
        errorMessage: formatZodError(bodyResult.error),
      });

      return res.status(400).json({
        error: {
          code: 'invalid_body',
          message: formatZodError(bodyResult.error),
        },
      });
    }

    const { fileId } = bodyResult.data;

    const deletionResult = await filesManager.deleteFile({
      baseFolder: getTenantScopedFolderName({ tenantId: configuration.tenant.tenantId }),
      fileId,
    });
    if (!deletionResult.success) {
      monitoring.logger.error('Delete file request failed', {
        errorName: deletionResult.error.code,
        errorMessage: deletionResult.error.message,
      });

      return res.status(500).json({
        error: {
          code: 'internal_error',
          message: 'Failed deleting file',
        },
      });
    }

    res.json({
      deleted: true,
    });
  };

const createGetGetSignedUrl =
  ({
    configuration,
    filesManager,
    monitoring,
  }: {
    configuration: Configuration;
    filesManager: FilesManager;
    monitoring: MonitoringContext;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
    const queryResult = GetDownloadUrlQuery.safeParse(req.query);
    if (!queryResult.success) {
      monitoring.logger.error('Invalid query parameters received for get GET signed request', {
        errorMessage: formatZodError(queryResult.error),
      });

      return res.status(400).json({
        error: {
          code: 'invalid_query',
          message: formatZodError(queryResult.error),
        },
      });
    }

    const { expiresIn, fileId, fileName } = queryResult.data;

    monitoring.logger.info('Request received for GET signed file download URL', {
      fileName,
    });

    const getPresignedUrlResult = await filesManager.getGetSignedUrl({
      baseFolder: getTenantScopedFolderName({ tenantId: configuration.tenant.tenantId }),
      contentDispositionType: 'inline',
      expiresIn,
      fileId,
      fileName,
    });
    if (!getPresignedUrlResult.success) {
      monitoring.logger.error('Get GET signed request URL failed', {
        errorName: getPresignedUrlResult.error.code,
        errorMessage: getPresignedUrlResult.error.message,
      });

      return res.status(500).json({
        error: {
          code: 'internal_error',
          message: 'Failed processing signed GET url',
        },
      });
    }

    res.json({
      url: getPresignedUrlResult.data.url,
    });
  };

const createGetPostSignedUrl =
  ({
    configuration,
    filesManager,
    monitoring,
  }: {
    configuration: Configuration;
    filesManager: FilesManager;
    monitoring: MonitoringContext;
  }) =>
  async (req: ExpressRequest, res: ExpressResponse) => {
    const bodyResult = GetPostSignedUrlBody.safeParse(req.body);
    if (!bodyResult.success) {
      monitoring.logger.error('Invalid body received for get POST signed request', {
        errorMessage: formatZodError(bodyResult.error),
      });

      return res.status(400).json({
        error: {
          code: 'invalid_body',
          message: formatZodError(bodyResult.error),
        },
      });
    }

    const { expiresIn, fileId, fileSize, fileType } = bodyResult.data;

    monitoring.logger.info('Request received for POST signed file upload URL', {
      fileSize,
      fileType,
      fileId,
    });

    const presignedUrlResult = await filesManager.getPostSignedUrl({
      baseFolder: getTenantScopedFolderName({ tenantId: configuration.tenant.tenantId }),
      fileId,
      expiresIn,
      fileSize,
      fileType,
    });

    if (!presignedUrlResult.success) {
      monitoring.logger.error('Get POST signed request URL failed', {
        errorName: presignedUrlResult.error.code,
        errorMessage: presignedUrlResult.error.message,
      });

      return res.status(500).json({
        error: {
          code: 'internal_error',
          message: 'Failed processing signed POST url',
        },
      });
    }

    const { url, fields } = presignedUrlResult.data;

    res.json({
      url,
      form_data: fields,
    });
  };

const getTenantScopedFolderName = ({ tenantId }: { tenantId: string }) => `tenants/${tenantId}`;

const configurationNotSupported =
  ({ monitoring }: { monitoring: MonitoringContext }) =>
  (req: ExpressRequest, res: ExpressResponse) => {
    monitoring.logger.error('Files route requested but configuration prevents its use', {
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    res.status(409).json({
      error: {
        code: 'not_supported',
        message: 'This route is not currently supported due to the files configuration in use',
      },
    });
  };

export const createFilesRouter = ({
  configuration,
  filesManager,
  monitoring,
}: {
  configuration: Configuration;
  filesManager: FilesManager | null;
  monitoring: MonitoringContext;
}): Router => {
  const router = createRouter();

  router
    .route('/')
    .post(
      express.json(),
      filesManager
        ? createGetPostSignedUrl({ configuration, filesManager, monitoring })
        : configurationNotSupported({ monitoring }),
    )
    .get(
      filesManager
        ? createGetGetSignedUrl({ configuration, filesManager, monitoring })
        : configurationNotSupported({ monitoring }),
    )
    .delete(
      filesManager
        ? createDeleteFile({ configuration, filesManager, monitoring })
        : configurationNotSupported({ monitoring }),
    );

  return router;
};
