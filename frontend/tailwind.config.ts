import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        moss: "#1d4ed8",
        mint: "#e8f0ff",
        sand: "#f8fbff"
      },
      boxShadow: { panel: "0 14px 35px rgba(30, 64, 175, 0.10)" }
    }
  },
  plugins: []
};

export default config;
