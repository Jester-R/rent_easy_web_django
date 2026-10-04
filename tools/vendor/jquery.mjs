/* Copies the pinned jQuery slim build into static/vendor/. */
import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../..");

const from = resolve(root, "node_modules/jquery/dist/jquery.slim.min.js");
const to = resolve(root, "static/vendor/jquery.slim.min.js");

await mkdir(dirname(to), { recursive: true });
await copyFile(from, to);
console.log("vendored ->", to);
