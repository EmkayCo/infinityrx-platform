import { describe, it, expect } from "vitest";
import {
  QA_MODE_COOKIE,
  parseQaMode,
  buildQaModeCookieValue,
} from "../qa/qa-mode-cookie.js";

describe("QA mode cookie utilities", () => {
  it("parseQaMode returns 'real' for undefined", () => {
    expect(parseQaMode(undefined)).toBe("real");
  });

  it("parseQaMode returns 'real' for invalid value", () => {
    expect(parseQaMode("invalid")).toBe("real");
  });

  it("parseQaMode returns 'stub' for 'stub'", () => {
    expect(parseQaMode("stub")).toBe("stub");
  });

  it("parseQaMode returns 'real' for 'real'", () => {
    expect(parseQaMode("real")).toBe("real");
  });

  it("buildQaModeCookieValue includes Secure when secure=true", () => {
    const val = buildQaModeCookieValue("stub", true);
    expect(val).toContain("Secure");
    expect(val).toContain(`${QA_MODE_COOKIE}=stub`);
  });

  it("buildQaModeCookieValue omits Secure when secure=false", () => {
    const val = buildQaModeCookieValue("real", false);
    expect(val).not.toContain("Secure");
  });

  it("QA_MODE_COOKIE constant is the expected string", () => {
    expect(QA_MODE_COOKIE).toBe("infinityrx-qa-mode");
  });
});
