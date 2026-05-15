import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(here, "..");

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else if (entry.endsWith(".ts") || entry.endsWith(".tsx")) files.push(full);
  }
  return files;
}

const FORBIDDEN_IMPORTS = [
  /from\s+["']next\//,
  /from\s+["']next-auth\//,
  /from\s+["']@auth\//,
  /require\(\s*["']next\//,
  /require\(\s*["']next-auth\//,
  /require\(\s*["']@auth\//,
];

describe("framework-agnostic enforcement — packages/ui", () => {
  const tsFiles = walk(SRC_DIR);

  it("there is at least one .ts/.tsx file under packages/ui/src/", () => {
    expect(tsFiles.length).toBeGreaterThan(0);
  });

  for (const file of tsFiles) {
    it(`${file.replace(SRC_DIR, "")} does not import Next.js / next-auth / @auth/*`, () => {
      const contents = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_IMPORTS) {
        expect(contents, `forbidden import matching ${pattern} in ${file}`).not.toMatch(pattern);
      }
    });
  }
});
