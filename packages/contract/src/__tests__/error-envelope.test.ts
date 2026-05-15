import { describe, it, expect } from "vitest";
import { ErrorEnvelopeSchema, isErrorEnvelope } from "../error-envelope.js";

describe("ErrorEnvelopeSchema", () => {
  it("accepts a well-formed envelope", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: {
        code: "VALIDATION_ERROR",
        message: "Field 'npi' must be 10 digits",
        field: "npi",
        correlation_id: "550e8400-e29b-41d4-a716-446655440000",
      },
    });
    expect(result.success).toBe(true);
  });

  it("accepts an envelope without optional field", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: {
        code: "INTERNAL_ERROR",
        message: "Something went wrong",
        correlation_id: "550e8400-e29b-41d4-a716-446655440000",
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects an envelope missing correlation_id", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: { code: "X", message: "Y" },
    });
    expect(result.success).toBe(false);
  });

  it("rejects an envelope with empty code", () => {
    const result = ErrorEnvelopeSchema.safeParse({
      error: { code: "", message: "Y", correlation_id: "550e8400-e29b-41d4-a716-446655440000" },
    });
    expect(result.success).toBe(false);
  });

  it("isErrorEnvelope narrows the type", () => {
    const candidate: unknown = {
      error: { code: "X", message: "Y", correlation_id: "550e8400-e29b-41d4-a716-446655440000" },
    };
    if (isErrorEnvelope(candidate)) {
      // TypeScript should narrow `candidate` to { error: { code: string, ... } }
      expect(candidate.error.code).toBe("X");
    } else {
      throw new Error("type guard should have narrowed");
    }
  });
});
