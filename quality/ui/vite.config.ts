import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join } from 'path';
import * as os from 'os';
import path from 'node:path';

const homeDir = os.homedir();
// change it if the quality folder is different
const defaultQualityFolder = join(homeDir, '.sema4x', 'quality');

function resolveFolder(p: string): string {
  // Only expand if it *starts* with "~/"
  if (p.startsWith('~/')) {
    const withoutTilde = p.slice(2); // drop the "~/"
    return path.resolve(os.homedir(), withoutTilde);
  }

  // Fallback: let Node handle absolute / relative paths normally
  return path.resolve(p);
}

// Custom plugin to serve quality_results files
function qualityResultsPlugin() {
  return {
    name: 'quality-results',
    configureServer(server: any) {
      server.middlewares.use('/api/quality_results', (req: any, res: any, next: any) => {
        console.log('Quality Home folder', req.headers['x-quality-home-folder']);
        const qualityFolder = req.headers['x-quality-home-folder'] ?? defaultQualityFolder;
        // Remove the /api/quality_results prefix and any leading slash
        const urlPath = req.url?.replace(/^\//, '') || '';
        const filePath = join(resolveFolder(qualityFolder), 'quality_results', urlPath);

        console.log('API Request:', req.url, '-> File Path:', filePath);

        try {
          if (existsSync(filePath)) {
            const stats = statSync(filePath);

            if (stats.isDirectory()) {
              // Directory listing for runs directory
              try {
                const files = readdirSync(filePath);
                const fileList = files
                  .filter((file) => file.endsWith('.json'))
                  .map((file) => `${file}`)
                  .join('\n');

                res.setHeader('Content-Type', 'text/plain');
                res.setHeader('Access-Control-Allow-Origin', '*');
                res.end(fileList);
              } catch (err) {
                console.error('Directory listing error:', err);
                res.statusCode = 500;
                res.end('Internal Server Error');
              }
            } else if (stats.isFile() && filePath.endsWith('.json')) {
              // Serve JSON file (including agents.json)
              try {
                const content = readFileSync(filePath, 'utf-8');
                res.setHeader('Content-Type', 'application/json');
                res.setHeader('Access-Control-Allow-Origin', '*');
                res.end(content);
              } catch (err) {
                console.error('File read error:', err);
                res.statusCode = 500;
                res.end('Internal Server Error');
              }
            } else {
              res.statusCode = 404;
              res.end('Not Found');
            }
          } else {
            console.log('File not found:', filePath);
            res.statusCode = 404;
            res.end('Not Found');
          }
        } catch (err) {
          console.error('Server error:', err);
          res.statusCode = 500;
          res.end('Internal Server Error');
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), qualityResultsPlugin()],
  server: {
    port: 5173,
    open: true,
    fs: {
      // Allow serving files from the parent directory (.datadir)
      allow: ['..', '../..'],
    },
  },
  define: {
    __DEV__: true,
  },
});
