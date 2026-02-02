import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  clean: true,
  dts: true,
  format: ['esm', 'cjs'],
  outDir: 'dist',
  outExtension: ({ format }) => {
    if (format === 'cjs') {
      return { js: '.cjs' };
    }
    return { js: '.js' };
  },
  target: 'es2020',
});
