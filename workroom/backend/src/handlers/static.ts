import { createReadStream } from 'node:fs';
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
