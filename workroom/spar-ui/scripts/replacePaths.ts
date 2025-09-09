import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const filename = fileURLToPath(import.meta.url);
const dirname = path.dirname(filename);

const ROOT = path.resolve(dirname, '../dist/');

/**
 * Add missing file extensions to imports
 */
const replacePaths = (directory) => {
  const currentPath = path.resolve(dirname, directory);
  const dir = fs.readdirSync(currentPath, 'utf8');

  dir.forEach((file) => {
    const currentFile = path.resolve(dirname, directory, file);
    if (fs.statSync(currentFile).isFile()) {
      if (['.js', '.ts'].indexOf(path.extname(currentFile)) > -1) {
        const content = fs.readFileSync(currentFile, 'utf8');
        const ext = path.extname(currentFile) === '.js' ? '.js' : '.d.ts';

        const modifiedContent = content.replace(/(from\s+['"])(.*?)(['"])/g, (match, p1, p2, p3) => {
          if (!(p2.startsWith('./') || p2.startsWith('../')) || p2.endsWith('.js')) {
            return match;
          }

          const directPath = `${p2}${ext}`;
          if (fs.existsSync(path.join(path.dirname(currentFile), directPath))) {
            return `${p1}${directPath}${p3}`;
          }

          const barrelPath = `${p2}/index${ext}`;
          if (fs.existsSync(path.join(path.dirname(currentFile), barrelPath))) {
            return `${p1}${barrelPath}${p3}`;
          }

          return match;
        });

        fs.writeFileSync(currentFile, modifiedContent);
      }
    } else {
      replacePaths(path.resolve(dirname, directory, file));
    }
  });
};

replacePaths(ROOT);
