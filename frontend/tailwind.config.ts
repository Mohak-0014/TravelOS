import type { Config } from "tailwindcss";

/**
 * ── TravelOS · "Daylight Voyage" design system ──────────────────────────────
 * A bright, airy daytime palette: soft cloud-white surfaces, clear sky-blue
 * accents, warm amber lights, and a coral pop. Token names are kept (space/
 * electric/gold/coral/emerald/slate/ink) so the existing class vocabulary
 * re-themes app-wide automatically.
 *
 *  - `space-*`   → light surface ramp; 950 = elevated/brightest (pure white)
 *  - `slate-*`   → dark text ramp on light (slate-100 = darkest heading)
 *  - `ink-*`     → dark hairline ramp, so `border-ink-900/8` reads on light
 *  - `electric-*`→ sky-blue accent (links, focus, secondary)
 *  - `gold-*`    → warm amber (primary CTA + sunlight)
 *  - `coral-*`   → coral/rose (tertiary accent)
 *  - `emerald-*` → success green
 *  - `purple-*`  → soft violet (cool gradients / glows)
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Surface ramp: soft cloud-white → lifted ───────────────────────
        space: {
          950: "#ffffff", // elevated (brightest, e.g. cards)
          900: "#f6f8fc", // main app background — soft cloud
          800: "#eef2fb", // alternating section background
          700: "#e4ebf7",
          600: "#d8e3f3",
          500: "#cbd9ee",
        },
        // ── Hairline ink: dark, so low-alpha borders read on light ────────
        ink: {
          900: "#0f172a",
          700: "#1e293b",
          500: "#475569",
          400: "#64748b",
          300: "#94a3b8",
        },
        glass: {
          DEFAULT: "rgba(255, 255, 255, 0.72)",
          light: "rgba(255, 255, 255, 0.55)",
          border: "rgba(15, 23, 42, 0.08)",
        },
        // ── Sky-blue (interactive accent) ─────────────────────────────────
        electric: {
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          glow: "rgba(14, 165, 233, 0.40)",
        },
        // ── Warm amber (primary CTA + sunlight) ───────────────────────────
        gold: {
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          glow: "rgba(245, 158, 11, 0.40)",
        },
        // ── Coral / rose (tertiary accent) ────────────────────────────────
        coral: {
          300: "#fda4af",
          400: "#fb7185",
          500: "#f43f5e",
          600: "#e11d48",
          glow: "rgba(244, 63, 94, 0.38)",
        },
        // ── Success green ─────────────────────────────────────────────────
        emerald: {
          400: "#10b981",
          500: "#059669",
          600: "#047857",
          glow: "rgba(5, 150, 105, 0.40)",
        },
        // ── Dark text ramp on light (slate-100 = darkest heading) ─────────
        slate: {
          50: "#0b1220", // strongest text
          100: "#0f172a", // primary headings
          200: "#1e293b",
          300: "#334155", // strong secondary
          400: "#475569", // body / muted
          500: "#64748b", // more muted
          600: "#94a3b8", // subtle
          700: "#cbd5e1", // faint
          800: "#e2e8f0", // divider
          900: "#eef2f7", // near-surface
          950: "#f8fafc",
        },
        // ── Soft violet (cool gradients / glows) ──────────────────────────
        purple: {
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
        },
      },
      fontFamily: {
        sans: ["var(--font-jakarta)", "system-ui", "sans-serif"],
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        mono: ["var(--font-jakarta)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "glass-gradient":
          "linear-gradient(135deg, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.60) 100%)",
        // electric-gradient is the brand fill → sky-blue (white text reads on it)
        "electric-gradient": "linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)",
        "sunset-gradient": "linear-gradient(135deg, #fb7185 0%, #fbbf24 55%, #f59e0b 100%)",
        "gold-gradient": "linear-gradient(135deg, #fcd34d 0%, #f59e0b 100%)",
        // bright daytime sky bands
        "sky-gradient": "linear-gradient(180deg, #aee3ff 0%, #d6efff 55%, #f6f8fc 100%)",
        "dawn-gradient":
          "linear-gradient(180deg, #8fd3ff 0%, #bfe8ff 40%, #e8f5ff 72%, #f6f8fc 100%)",
        "sand-gradient": "linear-gradient(180deg, #f6f8fc 0%, #eef2fb 100%)",
        "space-gradient":
          "radial-gradient(ellipse at top, #ffffff 0%, #f1f6fd 42%, #f6f8fc 100%)",
      },
      boxShadow: {
        glass: "0 10px 40px rgba(15, 23, 42, 0.08), 0 2px 10px rgba(15, 23, 42, 0.04)",
        "electric-sm": "0 6px 18px rgba(14, 165, 233, 0.30)",
        electric: "0 10px 36px rgba(14, 165, 233, 0.35), 0 2px 12px rgba(56, 189, 248, 0.20)",
        "gold-sm": "0 6px 18px rgba(245, 158, 11, 0.30)",
        gold: "0 10px 34px rgba(245, 158, 11, 0.42)",
        "coral-sm": "0 6px 18px rgba(244, 63, 94, 0.30)",
        "card-hover":
          "0 30px 60px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(14, 165, 233, 0.16)",
        soft: "0 10px 30px rgba(15, 23, 42, 0.08)",
      },
      backdropBlur: {
        glass: "16px",
        heavy: "28px",
      },
      animation: {
        "float-slow": "float 8s ease-in-out infinite",
        "float-medium": "float 6s ease-in-out infinite",
        "pulse-glow": "pulse-glow 3s ease-in-out infinite",
        "slide-up": "slide-up 0.5s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
        "cloud-drift": "cloud-drift 60s linear infinite",
        "cloud-drift-slow": "cloud-drift 90s linear infinite",
        sway: "sway 7s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
        twinkle: "twinkle 3s ease-in-out infinite",
        "spin-slow": "spin 26s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 12px rgba(245,158,11,0.35)" },
          "50%": { boxShadow: "0 0 28px rgba(245,158,11,0.65)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "cloud-drift": {
          "0%": { transform: "translateX(-10%)" },
          "100%": { transform: "translateX(110%)" },
        },
        sway: {
          "0%, 100%": { transform: "rotate(-2deg)" },
          "50%": { transform: "rotate(2deg)" },
        },
        twinkle: {
          "0%, 100%": { opacity: "0.2", transform: "scale(0.85)" },
          "50%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
