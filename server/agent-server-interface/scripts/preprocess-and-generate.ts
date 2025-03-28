import { writeFileSync, unlinkSync } from "fs";
import fetch from "node-fetch";
import { execSync } from "child_process";

const args = process.argv.slice(2);
const source = args[0];
const output = args[1] || "./src/schema.ts";
const tempFile = "./temp-openapi.json"; // Temporary file for the modified schema
const pathPrefix = "/api/v1"; // Prefix to add to paths

if (!source) {
  throw new Error("URL to OpenAPI schema not provided");
}

const updatePaths = (spec: any, prefix: string): any => {
  console.log(`Adding prefix "${prefix}" to all paths.`);
  const updatedPaths: Record<string, any> = {};
  for (const [path, value] of Object.entries(spec.paths)) {
    const newPath = `${prefix}${path}`;
    updatedPaths[newPath] = value;
  }
  spec.paths = updatedPaths;
  return spec;
};

const preprocessAndGenerate = async () => {
  try {
    console.log(`Fetching OpenAPI schema from ${source}...`);
    const response = await fetch(source);
    if (!response.ok) {
      throw new Error(`Failed to fetch schema: ${response.statusText}`);
    }
    const spec = await response.json();

    console.log("Modifying paths in the schema...");
    const updatedSpec = updatePaths(spec, pathPrefix);

    console.log(`Saving modified schema to ${tempFile}...`);
    writeFileSync(tempFile, JSON.stringify(updatedSpec, null, 2));

    console.log(`Generating TypeScript types in ${output}...`);
    execSync(`npx openapi-typescript ${tempFile} -o ${output}`, {
      stdio: "inherit",
    });

    console.log("Cleaning up temporary files...");
    unlinkSync(tempFile); // Delete the temporary file

    console.log("TypeScript types generated successfully!");
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
};

preprocessAndGenerate();
