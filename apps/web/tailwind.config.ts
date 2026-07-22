import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "var(--brand)",
        "brand-hover": "var(--brand-hover)",
        "brand-light": "var(--brand-light)",
        bg: "var(--bg-app)",
        "bg-card": "var(--bg-card)",
        "bg-popover": "var(--bg-popover)",
        text: "var(--text-main)",
        "text-muted": "var(--text-muted)",
        border: "var(--border-color)",
        amberline: "#d9922e",
        ink: "#111827",
        sage: "#275344",
        sand: "#f8f3ea"
      },
      fontFamily: {
        body: ["Aptos", "Segoe UI", "sans-serif"],
        display: ["Georgia", "serif"]
      }
    }
  },
  plugins: []
};

export default config;
