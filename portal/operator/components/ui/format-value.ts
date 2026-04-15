export type ValueFormat =
  | "text"
  | "number"
  | "currency"
  | "percent"
  | "date"
  | "npi"
  | "ndc"
  | "phone"
  | "status"
  | "raw";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-US");
const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatValue(value: unknown, format: ValueFormat = "text"): string {
  if (value === null || value === undefined || value === "") return "—";

  switch (format) {
    case "currency": {
      const n = toNumber(value);
      return n === null ? String(value) : currencyFormatter.format(n);
    }
    case "number": {
      const n = toNumber(value);
      return n === null ? String(value) : numberFormatter.format(n);
    }
    case "percent": {
      const n = toNumber(value);
      if (n === null) return String(value);
      // If value appears to already be a percentage (>1.5), treat it as such
      return percentFormatter.format(Math.abs(n) > 1.5 ? n / 100 : n);
    }
    case "date": {
      if (value instanceof Date) {
        return value.toLocaleDateString("en-US");
      }
      const d = new Date(String(value));
      return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString("en-US");
    }
    case "npi":
      return String(value).replace(/\D/g, "").padStart(10, "0").slice(0, 10);
    case "ndc": {
      const digits = String(value).replace(/\D/g, "").padStart(11, "0").slice(0, 11);
      return `${digits.slice(0, 5)}-${digits.slice(5, 9)}-${digits.slice(9, 11)}`;
    }
    case "phone": {
      const digits = String(value).replace(/\D/g, "");
      if (digits.length === 10) {
        return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
      }
      if (digits.length === 11 && digits.startsWith("1")) {
        return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
      }
      return String(value);
    }
    case "raw":
      return String(value);
    case "text":
    default:
      return String(value);
  }
}

export function compactCurrency(value: number | string | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return currencyFormatter.format(n);
}
