import { createReadStream, existsSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import express, { type NextFunction, type Request, type Response } from 'express';
import type { Configuration } from '../configuration.js';

export const createAssetServe = ({ root }: { root: string }) =>
  express.static(root, {
    redirect: false, // Don't redirect to trailing slash
    index: 'index.html', // Don't serve index.html
    fallthrough: true, // Fall-through to next handler
  });

export const createCompressionMiddleware =
  ({ root }: { root: string }) =>
  (req: Request, res: Response, next: NextFunction) => {
    const acceptEncoding = req.header('Accept-Encoding') ?? '';

    const metadata = getFileTypeMetadataForPath(req.path);
    if (!metadata) {
      return next();
    }

    if (acceptEncoding.includes('gzip')) {
      const gzipPath = resolve(root, req.path.slice(1) + '.gz');

      if (existsSync(gzipPath)) {
        res.set({
          'Content-Encoding': 'gzip',
          'Content-Type': metadata.contentType,
          Vary: 'Accept-Encoding',
        });

        const gzipStream = createReadStream(gzipPath);
        gzipStream.pipe(res);
        return;
      }
    }

    next();
  };

export const createIndexServe =
  ({ root }: { root: string }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    // Currently the `express.static` call handles all nested resources, but only
    // `index.html` on the ROOT route. This additional helper allows us to handle
    // `index.html` loads on non root routes like /<tenant-id>/home, for instance.

    const accepts = req.header('Accept') ?? '';
    if (accepts.indexOf('text/html') >= 0) {
      const indexStream = createReadStream(resolve(root, 'index.html'));
      res.set('Content-Type', 'text/html');
      indexStream.pipe(res);
      return;
    }

    return next();
  };

const getFileTypeMetadataForPath = (path: string): null | { contentType: string } => {
  const ext = path.split('.').pop() ?? '';

  switch (ext.toLowerCase()) {
    case 'mjs':
    case 'js':
      return {
        contentType: 'application/javascript',
      };
    case 'css':
      return {
        contentType: 'text/css',
      };
    case 'svg':
      return {
        contentType: 'image/svg+xml',
      };
    default:
      return null;
  }
};

export const initializeFrontendPlaceholders = async ({
  configuration,
  root,
}: {
  configuration: Configuration;
  root: string;
}): Promise<void> => {
  const indexHTMLPath = resolve(root, 'index.html');

  let indexContents = await readFile(indexHTMLPath, 'utf-8');
  indexContents = indexContents.replace(/DO_NOT_TOUCH_TENANT_ID_PLACEHOLDER/g, configuration.tenant.tenantId);

  await writeFile(indexHTMLPath, indexContents);
};
