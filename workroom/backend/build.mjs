import * as esbuild from 'esbuild';

await esbuild.build({
  entryPoints: ['src/index.ts'],
  outfile: 'dist/index.js',
  bundle: true,
  minify: false,
  platform: 'node',
  target: 'node24',
  format: 'esm',
  logLevel: 'info',
  external: ['path', 'vite', 'fsevents', 'esbuild'],
  inject: ['src/cjs-shim.ts'],
});
