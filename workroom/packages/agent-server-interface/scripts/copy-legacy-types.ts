import fs from 'fs';
import path from 'path';

function ensureDirectoryExists(directoryPath: string) {
  fs.mkdirSync(directoryPath, { recursive: true });
}

function copyFileOrThrow(sourceFilePath: string, destinationFilePath: string) {
  if (!fs.existsSync(sourceFilePath)) {
    throw new Error(`Source file not found: ${sourceFilePath}`);
  }
  fs.copyFileSync(sourceFilePath, destinationFilePath);
}

function main() {
  try {
    const packageRoot = path.resolve(__dirname, '..');

    const sourceDirectory = path.join(packageRoot, 'src', 'private', 'v1');
    const destinationDirectory = path.join(packageRoot, 'lib', 'private', 'v1');

    ensureDirectoryExists(destinationDirectory);

    const filesToCopy = ['schema.d.ts', 'spec.gen.d.ts'];

    for (const fileName of filesToCopy) {
      const sourceFilePath = path.join(sourceDirectory, fileName);
      const destinationFilePath = path.join(destinationDirectory, fileName);
      copyFileOrThrow(sourceFilePath, destinationFilePath);
    }

    console.log('Legacy types copied successfully.');
  } catch (error) {
    console.error(
      '[copy-legacy-types] Failed to copy legacy types:',
      error.message
    );
    process.exit(1);
  }
}

main();
