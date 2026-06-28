import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0b1020",
        panel: "#121a2e",
        edge: "#28324d",
      },
    },
  },
  plugins: [],
};

export default config;
