import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../shared/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0B1D3A",
          700: "#1B3A5C",
          500: "#2D5F8A",
        },
        teal: {
          600: "#0891B2",
          500: "#00B4D8",
          400: "#22D3EE",
        },
        ifx: {
          success: "#10B981",
          warning: "#F59E0B",
          error: "#EF4444",
          info: "#3B82F6",
          "bg-light": "#F8FAFC",
          "bg-dark": "#0F172A",
          "surface-light": "#FFFFFF",
          "surface-dark": "#1E293B",
          "border-light": "#E2E8F0",
          "border-dark": "#334155",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};

export default config;
