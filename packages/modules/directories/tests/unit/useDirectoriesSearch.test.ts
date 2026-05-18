// tests/unit/useDirectoriesSearch.test.ts
// Smoke test: verifies useDirectoriesSearch is exported from the search barrel.
// Full integration tests (with QueryClientProvider wrapper) are Plan E.
import { describe, it, expect } from "vitest";
import * as searchBarrel from "../../src/search/index.js";

describe("useDirectoriesSearch export", () => {
  it("is exported from src/search/index.ts", () => {
    expect(typeof searchBarrel.useDirectoriesSearch).toBe("function");
  });

  it("is also exported from the module root barrel (src/index.ts)", async () => {
    const root = await import("../../src/index.js");
    expect(typeof root.useDirectoriesSearch).toBe("function");
  });
});
