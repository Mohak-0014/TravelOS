import type { Config } from "tailwindcss";

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
        space: {
          950: "#04040f",
          900: "#080812",
          800: "#0c0c1e",
          700: "#0f1929",
          600: "#131f35",
          500: "#1a2a45",
        },
        glass: {
          DEFAULT: "rgba(15, 25, 41, 0.7)",
          light: "rgba(255, 255, 255, 0.04)",
          border: "rgba(255, 255, 255, 0.08)",
        },
        electric: {
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          glow: "rgba(59, 130, 246, 0.5)",
        },
        gold: {
          400: "#fbbf24",
          500: "#f59e0b",
          glow: "rgba(245, 158, 11, 0.4)",
        },
        coral: {
          400: "#fb7185",
          500: "#f43f5e",
          glow: "rgba(244, 63, 94, 0.4)",
        },
        emerald: {
          400: "#34d399",
          500: "#10b981",
          glow: "rgba(16, 185, 129, 0.4)",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "glass-gradient":
          "linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)",
        "electric-gradient": "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
        "gold-gradient": "linear-gradient(135deg, #f59e0b 0%, #f97316 100%)",
        "space-gradient":
          "radial-gradient(ellipse at top, #0f1929 0%, #080812 50%, #04040f 100%)",
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.06)",
        "electric-sm": "0 0 12px rgba(59, 130, 246, 0.4)",
        electric: "0 0 24px rgba(59, 130, 246, 0.5), 0 0 48px rgba(59, 130, 246, 0.2)",
        "gold-sm": "0 0 12px rgba(245, 158, 11, 0.4)",
        gold: "0 0 24px rgba(245, 158, 11, 0.5)",
        "coral-sm": "0 0 12px rgba(244, 63, 94, 0.4)",
        "card-hover":
          "0 20px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.08), 0 0 24px rgba(59,130,246,0.15)",
      },
      backdropBlur: {
        glass: "16px",
        heavy: "32px",
      },
      animation: {
        "float-slow": "float 8s ease-in-out infinite",
        "float-medium": "float 6s ease-in-out infinite",
        "pulse-glow": "pulse-glow 3s ease-in-out infinite",
        "slide-up": "slide-up 0.5s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
        orbit: "orbit 20s linear infinite",
        shimmer: "shimmer 2s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 12px rgba(59,130,246,0.4)" },
          "50%": { boxShadow: "0 0 32px rgba(59,130,246,0.8)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        orbit: {
          "0%": { transform: "rotate(0deg) translateX(120px) rotate(0deg)" },
          "100%": { transform: "rotate(360deg) translateX(120px) rotate(-360deg)" },
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
