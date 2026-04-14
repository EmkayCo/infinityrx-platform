import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  format as dateFnsFormat,
  formatDistanceToNow,
  parseISO,
  isValid,
} from "date-fns";

/** Tailwind class merging utility */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a money amount as "$1,234,567.89"
 * Input can be a string (from API / Decimal serialization), number (avoid), or Decimal-like object.
 * Always treat money as strings to avoid floating-point issues.
 */
export function formatDollars(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") {
    return "$0.00";
  }
  const numeric = typeof amount === "number" ? amount : parseFloat(String(amount));
  if (isNaN(numeric)) {
    return "$0.00";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
}

const ONES = [
  "",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
  "thirteen",
  "fourteen",
  "fifteen",
  "sixteen",
  "seventeen",
  "eighteen",
  "nineteen",
];

const TENS = [
  "",
  "",
  "twenty",
  "thirty",
  "forty",
  "fifty",
  "sixty",
  "seventy",
  "eighty",
  "ninety",
];

function threeDigitsToWords(n: number): string {
  if (n === 0) return "";
  if (n < 20) return ONES[n];
  if (n < 100) {
    return TENS[Math.floor(n / 10)] + (n % 10 !== 0 ? "-" + ONES[n % 10] : "");
  }
  const remainder = n % 100;
  const hundredsPart = ONES[Math.floor(n / 100)] + " hundred";
  if (remainder === 0) return hundredsPart;
  return hundredsPart + " " + threeDigitsToWords(remainder);
}

function integerToWords(n: number): string {
  if (n === 0) return "zero";
  const parts: string[] = [];
  const magnitudes = [
    { value: 1_000_000_000, name: "billion" },
    { value: 1_000_000, name: "million" },
    { value: 1_000, name: "thousand" },
    { value: 1, name: "" },
  ];
  let remaining = Math.abs(Math.floor(n));
  for (const { value, name } of magnitudes) {
    const count = Math.floor(remaining / value);
    remaining -= count * value;
    if (count > 0) {
      const words = threeDigitsToWords(count);
      parts.push(name ? `${words} ${name}` : words);
    }
  }
  return parts.join(" ");
}

/**
 * Convert a dollar amount to its verbal description.
 * "$13,247,891.23" → "thirteen million two hundred forty-seven thousand eight hundred ninety-one dollars and twenty-three cents"
 */
export function formatDollarsVerbal(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "zero dollars";
  const numeric = typeof amount === "number" ? amount : parseFloat(String(amount));
  if (isNaN(numeric)) return "zero dollars";

  const absValue = Math.abs(numeric);
  const dollars = Math.floor(absValue);
  const cents = Math.round((absValue - dollars) * 100);

  const dollarsText = integerToWords(dollars);
  const dollarWord = dollars === 1 ? "dollar" : "dollars";

  const prefix = numeric < 0 ? "negative " : "";

  if (cents === 0) {
    return `${prefix}${dollarsText} ${dollarWord}`;
  }
  const centsText = integerToWords(cents);
  const centWord = cents === 1 ? "cent" : "cents";
  return `${prefix}${dollarsText} ${dollarWord} and ${centsText} ${centWord}`;
}

/**
 * Format a date string or Date object as "Jan 14, 2026"
 */
export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? parseISO(date) : date;
  if (!isValid(d)) return "—";
  return dateFnsFormat(d, "MMM d, yyyy");
}

/**
 * Format a date string or Date object as "Jan 14, 2026 at 2:34 PM"
 */
export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? parseISO(date) : date;
  if (!isValid(d)) return "—";
  return dateFnsFormat(d, "MMM d, yyyy 'at' h:mm a");
}

/**
 * Format as relative time: "2 minutes ago", "1 hour ago", etc.
 */
export function formatRelative(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? parseISO(date) : date;
  if (!isValid(d)) return "—";
  return formatDistanceToNow(d, { addSuffix: true });
}

/**
 * Dollar amount classification for color scale
 */
export type DollarScale = "normal" | "bold" | "highlight";

export function getDollarScale(amount: number | string | null | undefined): DollarScale {
  if (amount === null || amount === undefined) return "normal";
  const numeric = typeof amount === "number" ? amount : parseFloat(String(amount));
  if (isNaN(numeric)) return "normal";
  if (numeric >= 1_000_000) return "highlight";
  if (numeric >= 100_000) return "bold";
  return "normal";
}
