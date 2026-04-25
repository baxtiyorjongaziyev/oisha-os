import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
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
