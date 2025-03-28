import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/**/!(*.test).ts"],
  format: ["esm"],
  splitting: true,
  sourcemap: false,
  clean: true,
  dts: true,
  bundle: true,
});
