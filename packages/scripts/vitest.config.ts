import { defineConfig } from "vitest/config";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const _require = createRequire(import.meta.url);

// ajv/dist/2020.js is in packages/scripts/node_modules/ in the main worktree but Vite
// resolves from the workspace root's node_modules which has ajv v6 (no dist/2020.js).
// Use an absolute alias pointing to the scripts-local ajv v8 dist file.
const ajvDist2020 = join(here, "node_modules", "ajv", "dist", "2020.js");
const ajvFormatsDist = (() => {
  try {
    return _require.resolve("ajv-formats");
  } catch {
    return "ajv-formats";
  }
})();

export default defineConfig({
  resolve: {
    alias: {
      "ajv/dist/2020.js": ajvDist2020,
      "ajv-formats": ajvFormatsDist,
    },
  },
  test: {
    include: ["*.test.ts"],
    environment: "node",
    deps: {
      // Tell vitest to let Node resolve ajv at runtime instead of Vite bundling it.
      // This is the correct fix for ESM/CJS package resolution in workspace setups.
      inline: [/ajv/],
    },
  },
});
