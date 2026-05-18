// tests/unit/ingestion/scheduleLabels.test.ts
// Pure-function tests for formatScheduleLabel and SCHEDULE_LABELS.
// 100% coverage target — every DEFAULT_SCHEDULES cron maps to a non-empty label.
// Verified against shared/data_ingestion/scheduler.py DEFAULT_SCHEDULES dict.
import { describe, it, expect } from "vitest";
import { formatScheduleLabel, SCHEDULE_LABELS } from "../../../src/ingestion/scheduleLabels.js";

// DEFAULT_SCHEDULES from shared/data_ingestion/scheduler.py — all cron values:
const DEFAULT_SCHEDULE_CRONS = [
  "0 2 * * *",        // fda_ndc
  "0 3 * * 1",        // cms_nadac
  "0 4 1 * *",        // fda_orange_book
  "0 3 * * 2",        // nppes
  "0 4 15 * *",       // nppes_monthly, cms_opt_out
  "0 5 15 * *",       // nppes_deactivation, fda_purple_book
  "0 4 1 1,4,7,10 *", // cms_asp
  "0 1 1-7 * 1",      // rxnorm
  "0 5 * * 3",        // fda_rems
  "0 6 * * *",        // fda_drug_shortages
  "0 2 20 * *",       // oig_leie
  "0 6 1 * *",        // dea_registrations
  "0 3 20 * *",       // sam_exclusions
  "0 2 15 4,10 *",    // icd10_cm
  "0 3 15 1,4,7,10 *",// hcpcs
] as const;

describe("SCHEDULE_LABELS", () => {
  it("covers all 15 DEFAULT_SCHEDULES cron expressions with non-empty labels", () => {
    for (const cron of DEFAULT_SCHEDULE_CRONS) {
      const label = SCHEDULE_LABELS[cron];
      expect(label, `Missing label for cron: ${cron}`).toBeTruthy();
      expect(label.length, `Empty label for cron: ${cron}`).toBeGreaterThan(0);
    }
  });

  it("has exactly 15 entries (one per non-null DEFAULT_SCHEDULES value)", () => {
    expect(Object.keys(SCHEDULE_LABELS).length).toBe(15);
  });
});

describe("formatScheduleLabel", () => {
  it("returns 'Manual only' for null cron", () => {
    expect(formatScheduleLabel(null)).toBe("Manual only");
  });

  it("maps '0 2 * * *' to 'Daily 2:00 AM' (fda_ndc schedule)", () => {
    expect(formatScheduleLabel("0 2 * * *")).toBe("Daily 2:00 AM");
  });

  it("maps '0 3 * * 1' to 'Weekly Mon 3:00 AM' (cms_nadac schedule)", () => {
    expect(formatScheduleLabel("0 3 * * 1")).toBe("Weekly Mon 3:00 AM");
  });

  it("maps '0 4 1 * *' to 'Monthly 1st 4:00 AM' (fda_orange_book schedule)", () => {
    expect(formatScheduleLabel("0 4 1 * *")).toBe("Monthly 1st 4:00 AM");
  });

  it("maps '0 4 1 1,4,7,10 *' to 'Quarterly 1st 4:00 AM' (cms_asp)", () => {
    expect(formatScheduleLabel("0 4 1 1,4,7,10 *")).toBe("Quarterly 1st 4:00 AM");
  });

  it("maps '0 1 1-7 * 1' to 'First Mon of month 1:00 AM' (rxnorm)", () => {
    expect(formatScheduleLabel("0 1 1-7 * 1")).toBe("First Mon of month 1:00 AM");
  });

  it("maps '0 2 15 4,10 *' to 'Apr/Oct 15th 2:00 AM' (icd10_cm)", () => {
    expect(formatScheduleLabel("0 2 15 4,10 *")).toBe("Apr/Oct 15th 2:00 AM");
  });

  it("maps '0 3 15 1,4,7,10 *' to 'Quarterly 15th 3:00 AM' (hcpcs)", () => {
    expect(formatScheduleLabel("0 3 15 1,4,7,10 *")).toBe("Quarterly 15th 3:00 AM");
  });

  it("returns raw cron string for unknown expressions (graceful fallback)", () => {
    expect(formatScheduleLabel("0 0 * * 0")).toBe("0 0 * * 0");
  });

  it("maps all 15 DEFAULT_SCHEDULES crons to non-empty strings", () => {
    for (const cron of DEFAULT_SCHEDULE_CRONS) {
      const label = formatScheduleLabel(cron);
      expect(label, `Missing label for: ${cron}`).toBeTruthy();
      expect(label).not.toBe("Manual only"); // non-null creons should not return manual only
    }
  });
});
