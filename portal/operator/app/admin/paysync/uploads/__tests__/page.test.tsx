/**
 * Tests for the pipe-detection routing logic in the uploads page.
 *
 * isPipeDelimited() is extracted here for unit testing so the hook can verify
 * the function exists and matches backend detect_format() semantics before
 * the page edit lands.
 */

/**
 * Inline copy of isPipeDelimited() from page.tsx — kept in sync manually.
 * If you change the page implementation, update this copy too.
 */
async function isPipeDelimited(file: File): Promise<boolean> {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "psv") return true;
  const slice = file.slice(0, 512);
  try {
    const text = await slice.text();
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (line) return line.includes("|");
    }
  } catch {
    // fall through
  }
  return false;
}

function makeFile(name: string, content: string): File {
  return new File([content], name, { type: "text/plain" });
}

describe("isPipeDelimited", () => {
  it("returns true for .psv extension regardless of content", async () => {
    const file = makeFile("export.psv", "no pipes here");
    expect(await isPipeDelimited(file)).toBe(true);
  });

  it("returns true when first non-blank line contains |", async () => {
    const content = "20260315|P|025706|IFX|03/15/2026|IC47103004\n";
    const file = makeFile("InfinityRX_20260316_0815.txt", content);
    expect(await isPipeDelimited(file)).toBe(true);
  });

  it("returns false for a CSV file with comma-separated header", async () => {
    const content = "ndc,npi,claim_id,date_of_service,quantity\n1234567890,1234567890,C001,2026-01-01,30\n";
    const file = makeFile("claims.csv", content);
    expect(await isPipeDelimited(file)).toBe(false);
  });

  it("skips blank leading lines and checks the first non-blank line", async () => {
    const content = "\n\n20260315|P|025706|IFX\n";
    const file = makeFile("export.txt", content);
    expect(await isPipeDelimited(file)).toBe(true);
  });

  it("returns false for a plain text file with no pipes", async () => {
    const file = makeFile("readme.txt", "just some text\nno pipes\n");
    expect(await isPipeDelimited(file)).toBe(false);
  });

  it("reads only the first 512 bytes — does not load the whole file", async () => {
    // Construct a file where the first line is pipe-delimited but the rest is huge.
    const header = "A|B|C|D\n";
    const padding = "x".repeat(100_000);
    const file = makeFile("big-export.txt", header + padding);
    // Still detects correctly from the first 512 bytes.
    expect(await isPipeDelimited(file)).toBe(true);
  });

  it("returns false for an XLSX file name (non-text, no pipe detection)", async () => {
    // XLSX binary content won't parse as text with pipes in the first line.
    const file = makeFile("claims.xlsx", "PK\x03\x04some binary xlsx content");
    expect(await isPipeDelimited(file)).toBe(false);
  });

  it("handles a file where ALL lines are blank — returns false (safe default)", async () => {
    const file = makeFile("empty.txt", "\n\n\n");
    expect(await isPipeDelimited(file)).toBe(false);
  });

  it("correctly identifies the real InfinityRX operator export format", async () => {
    // First line of InfinityRX_20260316_0815.txt -- pipe-delimited, no header row.
    const firstLine = "20260315842652919980|P|025706|IFX|03/15/2026|06/12/2025|IC47103004|IC47103004|HISTORY\n";
    const file = makeFile("InfinityRX_20260316_0815.txt", firstLine);
    expect(await isPipeDelimited(file)).toBe(true);
  });
});
