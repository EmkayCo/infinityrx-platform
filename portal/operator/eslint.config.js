// Flat ESLint config (ESLint 9+).
//
// KNOWN LIMITATION: the ideal config would spread eslint-config-next's flat
// arrays:
//
//   const nextCoreWebVitals = require("eslint-config-next/core-web-vitals");
//   const nextTypescript = require("eslint-config-next/typescript");
//   module.exports = [...nextCoreWebVitals, ...nextTypescript, { rules: ... }];
//
// …but as of 2026-04-14, the `eslint-plugin-react@7.37` vendored inside
// `eslint-config-next@16.2.3` uses `contextOrFilename.getFilename()` which
// was removed in ESLint 10. Linting with the full Next preset crashes with
// "TypeError: contextOrFilename.getFilename is not a function" inside
// eslint-plugin-react/lib/util/version.js. This is an upstream dep
// incompatibility; fix will land when Next bumps its vendored React plugin
// or when we can pin eslint-plugin-react separately.
//
// TODO: re-enable the full Next preset once the upstream issue is fixed,
// or pin `eslint-plugin-react` to a newer version in package.json.
//
// Meanwhile we run a minimal TypeScript-only flat config so `npm run lint`
// doesn't silently report success on a broken tool.
const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");
// react-hooks is vendored inside eslint-config-next; we load it only so
// that existing `// eslint-disable-next-line react-hooks/exhaustive-deps`
// directives in source files resolve without "Definition for rule not
// found" errors. We don't enable the rule itself since Next's full preset
// is currently broken (see comment above).
const path = require("path");
const reactHooksPlugin = require(
  path.join(
    __dirname,
    "node_modules/eslint-config-next/node_modules/eslint-plugin-react-hooks"
  )
);

module.exports = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      ".turbo/**",
      "public/**",
      "lib/data/sources/**",
      "next-env.d.ts",
      "tsconfig.tsbuildinfo",
    ],
  },
  {
    files: ["**/*.{ts,tsx}"],
    linterOptions: {
      // The minimal config below does not enable react-hooks/exhaustive-deps,
      // so existing // eslint-disable-next-line react-hooks/exhaustive-deps
      // directives are "unused" in a technical sense. Don't spam warnings
      // for them — they'll become active again when we restore the full
      // Next preset.
      reportUnusedDisableDirectives: "off",
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      "no-console": ["warn", { allow: ["warn", "error", "log"] }],
    },
  },
  {
    // Server-side store timing logs are intentional diagnostics.
    files: ["lib/data/**/*.{ts,tsx}"],
    rules: {
      "no-console": "off",
    },
  },
];
