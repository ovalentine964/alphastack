import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#0D1117",
          surface: "#161B22",
          border: "#30363D",
          green: "#00FF88",
          red: "#FF4444",
          text: "#E6EDF3",
          muted: "#8B949E",
          accent: "#58A6FF",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

export default config;
