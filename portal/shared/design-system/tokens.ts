export const ifxTokens = {
  colors: {
    navy: { 900: "#0B1D3A", 700: "#1B3A5C", 500: "#2D5F8A" },
    teal: { 600: "#0891B2", 500: "#00B4D8", 400: "#22D3EE" },
    success: "#10B981",
    warning: "#F59E0B",
    error: "#EF4444",
    info: "#3B82F6",
    bg: { light: "#F8FAFC", dark: "#0F172A" },
    surface: { light: "#FFFFFF", dark: "#1E293B" },
    border: { light: "#E2E8F0", dark: "#334155" },
    text: {
      primary: { light: "#1E293B", dark: "#F1F5F9" },
      secondary: { light: "#64748B", dark: "#94A3B8" },
    },
  },
  font: {
    display: "'Inter', system-ui, sans-serif",
    body: "'Inter', system-ui, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', monospace",
  },
  radius: { sm: "6px", md: "8px", lg: "12px" },
} as const;

export type IFXTokens = typeof ifxTokens;
