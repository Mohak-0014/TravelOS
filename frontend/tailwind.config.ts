import type { Config } from "tailwindcss";

/**
 * ── TravelOS · "Golden Hour" design system ──────────────────────────────────
 * A warm, light, wanderlust palette: sunrise sky, sandy cream, sunset coral,
 * golden amber, ocean teal. Token names are kept (space/electric/gold/coral/
 * emerald) so the existing class vocabulary re-themes app-wide automatically.
 *
 *  - `space-*`   → cream / sand surface ramp (was deep space)
 *  - `electric-*`→ sky azure accent (links, focus, secondary)
 *  - `coral-*`   → sunset coral (primary CTA)
 *  - `gold-*`    → golden amber
 *  - `emerald-*` → tropical teal-green (success)
 *  - `slate-*`   → REFLECTED ink ramp, so existing `text-slate-100` (was light
 *                  on dark) becomes dark ink on light, etc.
 *  - `purple-*`  → remapped to warm peach/coral so old cold gradients run warm
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
        // ── Surface ramp: warm sand → cream → white ───────────────────────
        space: {
          950: "#fffdf8", // lightest (elevated)
          900: "#fbf7f0", // main app background
          800: "#f4eee2", // alternating section background
          700: "#ece4d4",
          600: "#e3d9c6",
          500: "#d8ccb5",
        },
        // ── Ink: warm navy, used as the foreground "dark" ─────────────────
        ink: {
          900: "#14223d",
          700: "#27395b",
          500: "#475a78",
          400: "#64748b",
          300: "#8b99ad",
        },
        glass: {
          DEFAULT: "rgba(255, 255, 255, 0.7)",
          light: "rgba(255, 255, 255, 0.55)",
          border: "rgba(20, 34, 61, 0.08)",
        },
        // ── Sky azure (interactive accent) ────────────────────────────────
        electric: {
          300: "#9bd4f3",
          400: "#5bb8e8",
          500: "#36a3e0",
          600: "#2487c4",
          glow: "rgba(54, 163, 224, 0.4)",
        },
        // ── Golden amber ──────────────────────────────────────────────────
        gold: {
          300: "#ffd57d",
          400: "#ffc24d",
          500: "#f5a623",
          600: "#dd8a14",
          glow: "rgba(245, 166, 35, 0.4)",
        },
        // ── Sunset coral (primary) ────────────────────────────────────────
        coral: {
          300: "#ffb3a6",
          400: "#ff8a73",
          500: "#ff6b5c",
          600: "#ed4f3d",
          glow: "rgba(255, 107, 92, 0.4)",
        },
        // ── Tropical teal-green (success) ─────────────────────────────────
        emerald: {
          400: "#34c79a",
          500: "#1fa97a",
          600: "#178a63",
          glow: "rgba(31, 169, 122, 0.4)",
        },
        // ── Reflected slate ramp (light-on-dark → ink-on-light) ───────────
        slate: {
          50: "#0d1830",
          100: "#14223d", // primary headings
          200: "#1d2e4c",
          300: "#33425f", // strong secondary
          400: "#4f6079", // body / muted text
          500: "#6b7a90", // more muted
          600: "#94a3b4", // subtle
          700: "#bcc6d2", // faint
          800: "#dbe1e9", // light divider
          900: "#eef1f6", // near-surface
          950: "#f6f8fb",
        },
        // ── Warm remap of purple (kills cold gradients) ───────────────────
        purple: {
          300: "#ffd1a8",
          400: "#ffae84",
          500: "#ff8a73",
          600: "#f4684f",
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
          "linear-gradient(135deg, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.55) 100%)",
        // electric-gradient is the brand CTA → warm sunset (coral → amber)
        "electric-gradient": "linear-gradient(135deg, #ff6b5c 0%, #f5a623 100%)",
        "sunset-gradient": "linear-gradient(135deg, #ff6b5c 0%, #ffa34d 50%, #f5a623 100%)",
        "gold-gradient": "linear-gradient(135deg, #f5a623 0%, #ff8a3c 100%)",
        "sky-gradient": "linear-gradient(180deg, #cfeafd 0%, #eaf4fb 45%, #fef6ec 100%)",
        "dawn-gradient":
          "linear-gradient(180deg, #bfe3fb 0%, #ffe4cf 55%, #ffd2b0 78%, #fbf7f0 100%)",
        "sand-gradient": "linear-gradient(180deg, #fbf7f0 0%, #f4eee2 100%)",
        "space-gradient":
          "radial-gradient(ellipse at top, #d8eefc 0%, #eaf4fb 40%, #fbf7f0 100%)",
      },
      boxShadow: {
        glass: "0 10px 34px rgba(20, 34, 61, 0.08), 0 2px 8px rgba(20, 34, 61, 0.04)",
        "electric-sm": "0 6px 16px rgba(255, 107, 92, 0.28)",
        electric: "0 10px 30px rgba(255, 107, 92, 0.40), 0 2px 10px rgba(245, 166, 35, 0.20)",
        "gold-sm": "0 6px 16px rgba(245, 166, 35, 0.30)",
        gold: "0 10px 30px rgba(245, 166, 35, 0.40)",
        "coral-sm": "0 6px 16px rgba(255, 107, 92, 0.30)",
        "card-hover":
          "0 24px 50px rgba(20, 34, 61, 0.14), 0 0 0 1px rgba(20, 34, 61, 0.05)",
        soft: "0 8px 24px rgba(20, 34, 61, 0.07)",
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
        "sun-pulse": "sun-pulse 6s ease-in-out infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 12px rgba(255,107,92,0.4)" },
          "50%": { boxShadow: "0 0 28px rgba(255,107,92,0.75)" },
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
        "sun-pulse": {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "0.8", transform: "scale(1.05)" },
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
