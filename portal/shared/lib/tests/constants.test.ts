/**
 * Smoke tests for API_URLS default port assignments.
 * Verifies the defaults match the port map in
 * scripts/start-services/start-all-services.ps1.
 *
 * These tests catch future port-map drift between the start script
 * and the frontend constants before it causes silent 404s in dev.
 */
import { describe, it, expect } from "vitest";
import { API_URLS } from "../constants";

describe("API_URLS default ports", () => {
  // Use localhost defaults (env vars not set in test)
  it("reclaimrx defaults to port 8002", () => {
    expect(API_URLS.reclaimrx).toContain("8002");
  });

  it("billing defaults to port 8001", () => {
    expect(API_URLS.billing).toContain("8001");
  });

  it("medicalClaims defaults to port 8003", () => {
    expect(API_URLS.medicalClaims).toContain("8003");
  });

  it("memberManagement defaults to port 8004", () => {
    expect(API_URLS.memberManagement).toContain("8004");
  });

  it("reporting defaults to port 8012", () => {
    expect(API_URLS.reporting).toContain("8012");
  });

  it("dataiq defaults to port 8013", () => {
    expect(API_URLS.dataiq).toContain("8013");
  });

  it("edi defaults to port 8015", () => {
    expect(API_URLS.edi).toContain("8015");
  });

  it("adjudicationEngine defaults to port 8014", () => {
    expect(API_URLS.adjudicationEngine).toContain("8014");
  });

  it("pharmacyDirectory defaults to port 8009", () => {
    expect(API_URLS.pharmacyDirectory).toContain("8009");
  });

  it("prescriberDirectory defaults to port 8010", () => {
    expect(API_URLS.prescriberDirectory).toContain("8010");
  });

  it("drugDatabase defaults to port 8011", () => {
    expect(API_URLS.drugDatabase).toContain("8011");
  });
});
