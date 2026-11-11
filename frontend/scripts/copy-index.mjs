import { copyFileSync } from "node:fs";

copyFileSync(
  "dist/frontend/browser/index.csr.html",
  "dist/frontend/browser/index.html",
);
