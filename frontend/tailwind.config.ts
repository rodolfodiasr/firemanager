import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fff1f1",
          100: "#ffdfdf",
          500: "#e63946",
          600: "#c1121f",
          700: "#9d0208",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
