import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#0a0a0a",
          1: "#111111",
          2: "#1a1a1a",
          3: "#222222",
          4: "#2a2a2a",
        },
        // The accent is themeable: every `blue-*` and `accent` usage resolves to CSS
        // variables, so the default monochrome (black) scheme can be recolored in Settings
        // without touching components. Defaults live in index.css; presets in src/theme.ts.
        blue: {
          200: "var(--accent-200)",
          300: "var(--accent-300)",
          400: "var(--accent-400)",
          500: "var(--accent-500)",
          600: "var(--accent-600)",
          700: "var(--accent-700)",
        },
        accent: {
          DEFAULT: "var(--accent-500)",
          dim: "var(--accent-600)",
        },
        border: "#2a2a2a",
        muted: "#555555",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      // Island primitive tokens (defaults in index.css). Used by the <Island> wrapper.
      borderRadius: {
        island: "var(--island-radius)",
      },
      boxShadow: {
        island: "var(--island-shadow)",
      },
    },
  },
  plugins: [],
} satisfies Config;
