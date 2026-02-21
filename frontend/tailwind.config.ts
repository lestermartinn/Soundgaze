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
        // Design token palette — use as bg-canvas, text-accent, border-divider, etc.
        canvas:  "#08090c",
        surface: "#111318",
        divider: "#1e2230",
        accent:  "#7c6af7",
        primary: "#e8eaf0",
        muted:   "#6b7280",
      },
      fontFamily: {
        mono: ["Courier New", "Courier", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
