import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // --- Soundgaze Design System ---
        "spotify-green": "#1DB954",
        "near-black":    "#0a0a0a",
        "spotify-black": "#191414",
        "off-white":     "#f5f5f5",

        // --- Legacy tokens (mapped to new palette for existing code) ---
        canvas:  "#0a0a0a",   // page / Three.js canvas background
        surface: "#191414",   // navbar, dark panels
        divider: "#2a2a2a",   // subtle borders on dark surfaces
        accent:  "#1DB954",   // green CTAs and highlights
        primary: "#FFFFFF",   // main text on dark backgrounds
        muted:   "#6b7280",   // secondary / placeholder text
      },
      fontFamily: {
        sans: ["var(--font-syne)", "sans-serif"],
        syne: ["var(--font-syne)", "sans-serif"],
        mono: ["Courier New", "Courier", "monospace"],
      },
      keyframes: {
        marquee: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "marquee-slow":   "marquee 30s linear infinite",
        "marquee-medium": "marquee 20s linear infinite",
        "marquee-fast":   "marquee 12s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
