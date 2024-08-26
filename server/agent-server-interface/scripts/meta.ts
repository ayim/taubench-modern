import { writeFileSync } from "fs";

const args = process.argv.slice(2);
const source = args[0];

if (!source) {
  throw new Error("URL to OpenAPI schema not provided");
}

const writeMeta = async () => {
  const response = await fetch(source);
  const json = await response.json();
  writeFileSync(
    "./src/meta.ts",
    `export const meta = ${JSON.stringify(json.info, null, 4)};`
  );
};

writeMeta();
