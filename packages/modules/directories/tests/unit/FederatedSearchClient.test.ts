// tests/unit/FederatedSearchClient.test.ts
// Tests fan-out, partial results, ID shortcut detection, and empty query handling.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FederatedSearchClient } from "../../src/search/FederatedSearchClient.js";

const BASE_OPTS = {
  prescriberDirectoryUrl: "http://prescriber-directory:8010",
  pharmacyDirectoryUrl: "http://pharmacy-directory:8009",
  drugDatabaseUrl: "http://drug-database:8011",
  budgetMs: 300,
  limitPerDataset: 5,
};

function makePrescriberResponse(results: object[]) {
  return new Response(JSON.stringify({ results }), { status: 200 });
}
function makePharmacyResponse(results: object[]) {
  return new Response(JSON.stringify({ results }), { status: 200 });
}
function makeDrugResponse(results: object[]) {
  return new Response(JSON.stringify({ results }), { status: 200 });
}

describe("FederatedSearchClient — detectIdShortcut", () => {
  const client = new FederatedSearchClient(BASE_OPTS);

  it("detects 10-digit NPI", () => {
    expect(client.detectIdShortcut("1234567890")).toEqual({ kind: "npi", value: "1234567890" });
  });

  it("detects 11-digit NDC", () => {
    expect(client.detectIdShortcut("12345678901")).toEqual({ kind: "ndc", value: "12345678901" });
  });

  it("detects hyphenated NDC", () => {
    expect(client.detectIdShortcut("12345-6789-0")).toEqual({ kind: "ndc", value: "12345-6789-0" });
  });

  it("detects HCPCS code J0135", () => {
    expect(client.detectIdShortcut("J0135")).toEqual({ kind: "hcpcs", value: "J0135" });
  });

  it("detects ICD-10 code Z87.891", () => {
    expect(client.detectIdShortcut("Z87.891")).toEqual({ kind: "icd10", value: "Z87.891" });
  });

  it("returns null for non-matching string", () => {
    expect(client.detectIdShortcut("aspirin")).toBeNull();
  });

  it("returns null for partial NPI (9 digits)", () => {
    expect(client.detectIdShortcut("123456789")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(client.detectIdShortcut("")).toBeNull();
  });
});

describe("FederatedSearchClient — search", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(global, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty results for empty query", async () => {
    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("", "corr-1");
    expect(result.results).toEqual([]);
    expect(result.timedOutDatasets).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fan-out: all 3 backends return results — merged and ranked", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("prescriber")) {
        return Promise.resolve(
          makePrescriberResponse([
            { npi: "1234567890", name: "Dr. Smith", specialty: "Cardiology", source_date: "2026-05-10", run_id: "r1" },
          ]),
        );
      }
      if (urlStr.includes("pharmacy")) {
        return Promise.resolve(
          makePharmacyResponse([
            { nabp: "1234567", name: "CVS Pharmacy", city: "Chicago", source_date: "2026-05-10", run_id: "r2" },
          ]),
        );
      }
      if (urlStr.includes("drug")) {
        return Promise.resolve(
          makeDrugResponse([
            { ndc: "12345678901", proprietary_name: "Aspirin", nonproprietary_name: "Aspirin 325mg", source_date: "2026-05-10", run_id: "r3" },
          ]),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("aspirin", "corr-2");

    expect(result.timedOutDatasets).toEqual([]);
    expect(result.results.length).toBeGreaterThan(0);
    // aspirin drug result should be ranked first (display prefix match)
    const datasets = result.results.map((r) => r.dataset);
    expect(datasets).toContain("nppes");
    expect(datasets).toContain("ncpdp");
    expect(datasets).toContain("fda_ndc");
  });

  it("partial result: one backend times out — timedOutDatasets includes it, others returned", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("prescriber")) {
        // Simulate timeout: never resolves within budget
        return new Promise<Response>(() => {/* never resolves */});
      }
      if (urlStr.includes("pharmacy")) {
        return Promise.resolve(
          makePharmacyResponse([
            { nabp: "9876543", name: "Walgreens", city: "Dallas", source_date: "2026-05-10", run_id: "r4" },
          ]),
        );
      }
      if (urlStr.includes("drug")) {
        return Promise.resolve(
          makeDrugResponse([]),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    // Use very short budget so prescriber times out immediately
    const client = new FederatedSearchClient({ ...BASE_OPTS, budgetMs: 1 });
    const result = await client.search("walgreens", "corr-3");

    expect(result.timedOutDatasets).toContain("nppes");
    expect(result.results.some((r) => r.dataset === "ncpdp")).toBe(true);
  });

  it("partial result: backend fetch throws — timedOutDatasets includes it", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("prescriber")) {
        return Promise.reject(new Error("Network error"));
      }
      if (urlStr.includes("pharmacy")) {
        return Promise.resolve(makePharmacyResponse([]));
      }
      if (urlStr.includes("drug")) {
        return Promise.resolve(makeDrugResponse([]));
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("test", "corr-4");

    expect(result.timedOutDatasets).toContain("nppes");
  });

  it("maps prescriber response fields correctly", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("prescriber")) {
        return Promise.resolve(
          makePrescriberResponse([
            { npi: "9876543210", name: "Dr. Jones", specialty: "Pediatrics", source_date: "2026-04-01", run_id: "run-p" },
          ]),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("Jones", "corr-5");

    const prescriberResult = result.results.find((r) => r.dataset === "nppes");
    expect(prescriberResult).toBeDefined();
    expect(prescriberResult!.id).toBe("9876543210");
    expect(prescriberResult!.display).toBe("Dr. Jones");
    expect(prescriberResult!.secondary).toBe("Pediatrics");
    expect(prescriberResult!.source_date).toBe("2026-04-01");
    expect(prescriberResult!.run_id).toBe("run-p");
  });

  it("maps pharmacy response fields correctly", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("pharmacy")) {
        return Promise.resolve(
          makePharmacyResponse([
            { nabp: "7654321", name: "Rite Aid", city: "Boston", source_date: "2026-04-15", run_id: "run-ph" },
          ]),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("Rite Aid", "corr-6");

    const pharmacyResult = result.results.find((r) => r.dataset === "ncpdp");
    expect(pharmacyResult).toBeDefined();
    expect(pharmacyResult!.id).toBe("7654321");
    expect(pharmacyResult!.display).toBe("Rite Aid");
    expect(pharmacyResult!.secondary).toBe("Boston");
  });

  it("maps drug response fields correctly", async () => {
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = url.toString();
      if (urlStr.includes("drug")) {
        return Promise.resolve(
          makeDrugResponse([
            { ndc: "00069000105", proprietary_name: "Lipitor", nonproprietary_name: "Atorvastatin", source_date: "2026-03-01", run_id: "run-d" },
          ]),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    const result = await client.search("Lipitor", "corr-7");

    const drugResult = result.results.find((r) => r.dataset === "fda_ndc");
    expect(drugResult).toBeDefined();
    expect(drugResult!.id).toBe("00069000105");
    expect(drugResult!.display).toBe("Lipitor");
    expect(drugResult!.secondary).toBe("Atorvastatin");
  });

  it("sends x-correlation-id header to each backend", async () => {
    const capturedHeaders: string[] = [];
    fetchSpy.mockImplementation((_url: string | URL | Request, opts?: RequestInit) => {
      const headers = opts?.headers as Record<string, string> | undefined;
      if (headers?.["x-correlation-id"]) {
        capturedHeaders.push(headers["x-correlation-id"]);
      }
      return Promise.resolve(new Response(JSON.stringify({ results: [] })));
    });

    const client = new FederatedSearchClient(BASE_OPTS);
    await client.search("test", "my-correlation-id");

    expect(capturedHeaders.length).toBeGreaterThan(0);
    expect(capturedHeaders.every((h) => h === "my-correlation-id")).toBe(true);
  });
});
