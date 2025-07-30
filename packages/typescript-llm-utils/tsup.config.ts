import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/**/!(*.test).ts'],
  format: ['cjs'],
  splitting: true,
  sourcemap: false,
  clean: true,
  dts: true,
  bundle: true,
});
