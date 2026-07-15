import type { Config } from "tailwindcss";

/**
 * ── TravelOS · "Night Flight" design system ─────────────────────────────────
 * Cinematic dark: deep midnight surfaces, full-bleed photography, frosted
 * glass panels, one warm sunset accent that glows against the dark.
 *
 *  - `paper`      → app background, deep midnight (#0B0F14) — name kept from
 *                   the previous system so page-level `bg-paper` still means
 *                   "app background" everywhere
 *  - `surface-*`  → elevated card / panel fills
 *  - `ink-*`      → text ramp, INVERTED for dark: 900 = primary (near-white),
 *                   300 = faint, 100 = subtle dark fill. `border-ink-900/10`
 *                   therefore reads as a white hairline — the app-wide idiom.
 *  - `accent-*`   → sunset amber-coral, the single warm brand accent
 *  - `success/warning/danger/info-*` → brightened for dark ground; tints are
 *                   dark washes meant to sit under their DEFAULT-colored text
 */
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#0B0F14",
        surface: {
          DEFAULT: "#11161D", // cards, panels
          raised: "#161D26", // hover / elevated wells, active pills
        },
        accent: {
          DEFAULT: "#FF9E64", // sunset amber-coral
          deep: "#FF8443", // hover/active
          tint: "#2C1E14", // selected/active background wash (dark warm)
        },
        success: { DEFAULT: "#3ECF8E", deep: "#5FE0A5", tint: "#11271C" },
        warning: { DEFAULT: "#FFC46B", deep: "#FFD28A", tint: "#2B2212" },
        danger: { DEFAULT: "#FF6B5B", deep: "#FF8A7C", tint: "#2E1512" },
        info: { DEFAULT: "#6BB6FF", deep: "#8AC6FF", tint: "#13202E" },
        // Text ramp (inverted for dark: 900 light → 100 dark fill)
        ink: {
          900: "#F2F5F7", // primary text / headings
          800: "#DEE4E9",
          700: "#C5CDD5",
          600: "#A7B1BC", // secondary text
          500: "#8893A1",
          400: "#6C7787", // muted text
          300: "#4B5566", // faint text / placeholders
          200: "#293241", // dividers on surface
          100: "#191F29", // subtle fills (chips, wells)
        },
      },
      fontFamily: {
        sans: ["var(--font-instrument)", "system-ui", "sans-serif"],
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        mono: ["var(--font-spline-mono)", "ui-monospace", "monospace"],
      },
      borderColor: {
        DEFAULT: "rgba(255, 255, 255, 0.08)", // hairline
      },
      backgroundImage: {
        // The brand gradient — CTAs, active states, gradient text (with bg-clip-text)
        sunset: "linear-gradient(135deg, #FFC46B 0%, #FF9E64 45%, #FF5D73 100%)",
        // Subtle vertical fade used to blend photo sections into the page bg
        "fade-b": "linear-gradient(to bottom, transparent, #0B0F14)",
        "fade-t": "linear-gradient(to top, transparent, #0B0F14)",
      },
      boxShadow: {
        lift: "0 8px 28px rgba(0, 0, 0, 0.5), 0 2px 8px rgba(0, 0, 0, 0.35)",
        overlay: "0 32px 80px rgba(0, 0, 0, 0.65), 0 8px 24px rgba(0, 0, 0, 0.5)",
        glow: "0 0 28px rgba(255, 158, 100, 0.28)",
        "glow-lg": "0 0 64px rgba(255, 158, 100, 0.32)",
      },
    },
  },
  plugins: [],
};

export default config;
