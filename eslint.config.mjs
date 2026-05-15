// PLACEHOLDER — Plan A Task 1.
// SP-0 Plan A Task 5 replaces this with the full workspace-root ESLint flat
// config that implements SD-4 §4 import-boundary rules (no-restricted-imports
// + no-restricted-syntax bypass-path selectors + import/no-restricted-paths
// zone array). Until Task 5 lands, this placeholder lets `npm run lint:root`
// exit 0 instead of failing with "no eslint config found".

import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      // workspace packages with their own ESLint configs
      "portal/**",
      // Python virtualenvs anywhere in the tree
      "**/.venv/**",
      "**/.venv*//**",
      // build / generated artifacts
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/playwright-report/**",
      "**/test-results/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
);
