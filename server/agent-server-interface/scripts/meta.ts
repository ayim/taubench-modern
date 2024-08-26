import { writeFileSync, readFileSync } from "fs";

const args = process.argv.slice(2);
const source = args[0];

if (!source) {
  throw new Error("URL to OpenAPI schema not provided");
}

const writeMeta = async () => {
  const response = await fetch(source);
  const meta = await response.json();

  writeFileSync(
    "./src/meta.ts",
    `export const meta = ${JSON.stringify(meta.info, null, 2)};`
  );

  const packageFile = readFileSync("./package.json", "utf-8");
  const packageJson = JSON.parse(packageFile);

  packageJson.version = meta.info.version;

  writeFileSync("./package.json", JSON.stringify(packageJson, null, 2));
};

writeMeta();
