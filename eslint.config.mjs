// Workspace-root ESLint flat config.
// Authority: SD-4 §4 (composition spike, `0b3c9d7`) for import-boundary enforcement.
// Plan A scaffolds the rule shape with empty zones; Plan D's
// scripts/generate-eslint-zones.ts populates `GENERATED_MODULE_ZONES`
// from packages/modules/* as those modules are added.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import importPlugin from "eslint-plugin-import";

// Generated composition-zone enforcement (SD-4 §4).
// STILL-OPEN-3 fix: import .mjs (not .js or .ts) — generator emits pure ESM .mjs
// which Node can import at runtime without a TS loader.
// STILL-OPEN-3b fix: fallback is the sentinel constant, not [] — avoids minItems:1 schema
// violation from eslint-plugin-import; console.warn makes the missing-file case visible.
// Run `npm run prebuild` (or `npm run composition:check`) to populate the generated file.
const GENERATED_MODULE_ZONES_SENTINEL = [
  {
    target: "./packages/shell/src/_generated/**",
    from: "./packages/shell/src/_generated/**",
    message: "SENTINEL — replaced by generate-eslint-zones.ts output (run npm run prebuild).",
  },
];
let GENERATED_MODULE_ZONES = GENERATED_MODULE_ZONES_SENTINEL;
try {
  const generated = await import("./packages/shell/src/_generated/eslint-zones.mjs");
  GENERATED_MODULE_ZONES = generated.GENERATED_MODULE_ZONES;
} catch {
  // Cold checkout — zones not yet generated. ESLint runs with sentinel (no-op).
  console.warn("[eslint] WARN: packages/shell/src/_generated/eslint-zones.mjs not found. Run npm run prebuild.");
}

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/playwright-report/**",
      "**/test-results/**",
      "**/.venv/**",
      // Agent-tool worktrees live under .claude/worktrees/agent-*/ and contain
      // a full repo checkout — linting them double-counts every file and
      // surfaces stale findings from in-flight subagent work.
      ".claude/worktrees/**",
      "portal/operator/**",
      // portal/shared is a workspace with its own linting concerns (next-auth
      // imports are intentional there — see Block B comment). Root config
      // covers packages/** only; portal/shared is linted as part of the
      // portal/operator workspace (which has its own eslint config).
      "portal/shared/**",
      // Plan D will replace this ignore with a `files:` allow-only for
      // `packages/shell/src/_generated/**` references to `@infinityrx/module-*`.
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,

  // ── Block A: @infinityrx/module-* boundary applies EVERYWHERE in the workspace.
  // (The `import/no-restricted-paths` zones at the bottom complement this for
  //  relative/alias bypass paths once Plan D populates them.)
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    plugins: { import: importPlugin },
    settings: {
      "import/resolver": {
        typescript: { project: ["./tsconfig.json", "./packages/scripts/tsconfig.json"] },
      },
    },
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [
          { group: ["@infinityrx/module-*"],
            message: "Modules are referenced ONLY from packages/shell/src/_generated/. Direct imports break composition isolation (SD-4 §2)." },
        ],
      }],

      // Bypass paths — each must be covered for THREE specifier shapes:
      //   1. Package name      : "@infinityrx/module-<name>"
      //   2. Relative traversal: "(../)+modules/<name>/..." or "(../)+packages/modules/<name>/..."
      //   3. TS path alias     : "@/modules/<name>" or "@modules/<name>"
      // Across FIVE forms: ImportDeclaration (incl. side-effect), ExportAllDeclaration,
      // ExportNamedDeclaration (with source), ImportExpression (dynamic import), and require() CallExpression.
      "no-restricted-syntax": ["error",
        // ── Shape 1: @infinityrx/module-* package specifier (dynamic forms) ──
        { selector: "ExportAllDeclaration[source.value=/^@infinityrx\\/module-/]",
          message: "Re-exporting from @infinityrx/module-* defeats composition isolation." },
        { selector: "ExportNamedDeclaration[source.value=/^@infinityrx\\/module-/]",
          message: "Named re-exports from @infinityrx/module-* defeat composition isolation." },
        { selector: "ImportExpression[source.value=/^@infinityrx\\/module-/]",
          message: "Dynamic import() of @infinityrx/module-* defeats composition isolation." },
        { selector: "CallExpression[callee.name='require'][arguments.0.value=/^@infinityrx\\/module-/]",
          message: "require() of @infinityrx/module-* defeats composition isolation." },
        { selector: "ImportDeclaration[specifiers.length=0][source.value=/^@infinityrx\\/module-/]",
          message: "Side-effect imports of @infinityrx/module-* defeat composition isolation." },

        // ── Shape 2: relative-path traversal `(../)+modules/<name>` or `(../)+packages/modules/<name>` ──
        { selector: "ImportDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "Relative-path traversal into a sibling module is forbidden. Use packages/contract." },
        { selector: "ExportAllDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "Relative re-export from a sibling module is forbidden." },
        { selector: "ExportNamedDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "Relative named re-export from a sibling module is forbidden." },
        { selector: "ImportExpression[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "Dynamic import() via relative traversal into a sibling module is forbidden." },
        { selector: "CallExpression[callee.name='require'][arguments.0.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "require() via relative traversal into a sibling module is forbidden." },
        { selector: "ImportDeclaration[specifiers.length=0][source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
          message: "Side-effect import via relative traversal into a sibling module is forbidden." },

        // ── Shape 3: TS path-alias forms `@/modules/<name>` or `@modules/<name>` ──
        { selector: "ImportDeclaration[source.value=/^@\\/?modules\\//]",
          message: "TS path-alias references to modules are forbidden. Use packages/contract." },
        { selector: "ExportAllDeclaration[source.value=/^@\\/?modules\\//]",
          message: "TS path-alias re-export from a module is forbidden." },
        { selector: "ExportNamedDeclaration[source.value=/^@\\/?modules\\//]",
          message: "TS path-alias named re-export from a module is forbidden." },
        { selector: "ImportExpression[source.value=/^@\\/?modules\\//]",
          message: "TS path-alias dynamic import() of a module is forbidden." },
        { selector: "CallExpression[callee.name='require'][arguments.0.value=/^@\\/?modules\\//]",
          message: "TS path-alias require() of a module is forbidden." },
        { selector: "ImportDeclaration[specifiers.length=0][source.value=/^@\\/?modules\\//]",
          message: "TS path-alias side-effect import of a module is forbidden." },
      ],

      // Force `import type` discrimination so the audit can distinguish type-only references from runtime ones
      "@typescript-eslint/consistent-type-imports": ["error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" }],

      // Plan D (STILL-OPEN-3): zones loaded from _generated/eslint-zones.mjs via dynamic import
      // above. Falls back to GENERATED_MODULE_ZONES_SENTINEL (no-op zone) on cold checkout.
      "import/no-restricted-paths": ["error", { zones: GENERATED_MODULE_ZONES }],
    },
  },

  // ── Block B: framework-agnostic import ban scoped to packages/** only.
  // Plan A scope: applies ONLY to packages/** (the NEW SP-0 workspaces).
  // portal/shared/** is DELIBERATELY excluded because it currently imports
  // next-auth/react + next-auth/providers/credentials. portal/operator/**
  // is excluded by the global ignore above because Next.js is allowed there.
  // When Plan C migrates portal/shared into packages/**, the ban applies then.
  {
    files: [
      "packages/**/*.{ts,tsx,js,jsx,mjs,cjs}",
    ],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [
          { group: ["@infinityrx/module-*"],
            message: "Modules are referenced ONLY from packages/shell/src/_generated/. Direct imports break composition isolation (SD-4 §2)." },
          { group: ["next/*", "next-auth/*", "@auth/*"],
            message: "Framework-specific imports are forbidden in packages/**. Move usage into a thin adapter at portal/operator/app/ (SD-2)." },
        ],
      }],
    },
  },
);
