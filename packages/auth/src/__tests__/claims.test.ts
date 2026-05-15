import { describe, it, expect } from "vitest";
import { AccessClaimsSchema, RefreshClaimsSchema } from "../claims.js";

const validAccess = {
  sub: "550e8400-e29b-41d4-a716-446655440000",
  tid: "550e8400-e29b-41d4-a716-446655440001",
  roles: ["platform_admin"],
  typ: "access" as const,
  iat: 1700000000,
  exp: 1700000900,
  jti: "550e8400-e29b-41d4-a716-446655440002",
  iss: "infinityrx" as const,
  aud: "infinityrx-backend" as const,
  env: "production" as const,
};

const validRefresh = {
  sub: "550e8400-e29b-41d4-a716-446655440000",
  typ: "refresh" as const,
  iat: 1700000000,
  exp: 1700028800,
  jti: "550e8400-e29b-41d4-a716-446655440003",
  iss: "infinityrx" as const,
  aud: "infinityrx-backend" as const,
  env: "production" as const,
};

describe("AccessClaimsSchema", () => {
  it("accepts a valid access-token claim set", () => {
    expect(AccessClaimsSchema.safeParse(validAccess).success).toBe(true);
  });
  it("accepts empty roles array", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, roles: [] }).success).toBe(true);
  });
  it("rejects missing tid (REQUIRED for access)", () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { tid: _omit, ...withoutTid } = validAccess;
    expect(AccessClaimsSchema.safeParse(withoutTid).success).toBe(false);
  });
  it("rejects typ=refresh on access schema", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, typ: "refresh" }).success).toBe(false);
  });
  it("rejects iss=wrong on access schema", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, iss: "wrong" }).success).toBe(false);
  });
  it("rejects env outside the enum", () => {
    expect(AccessClaimsSchema.safeParse({ ...validAccess, env: "staging" }).success).toBe(false);
  });
});

describe("RefreshClaimsSchema", () => {
  it("accepts a valid refresh-token claim set", () => {
    expect(RefreshClaimsSchema.safeParse(validRefresh).success).toBe(true);
  });
  it("rejects refresh with tid (refresh tokens MUST NOT have tid)", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, tid: validAccess.tid }).success).toBe(false);
  });
  it("rejects refresh with roles (refresh tokens MUST NOT have roles)", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, roles: ["x"] }).success).toBe(false);
  });
  it("rejects typ=access on refresh schema", () => {
    expect(RefreshClaimsSchema.safeParse({ ...validRefresh, typ: "access" }).success).toBe(false);
  });
});
