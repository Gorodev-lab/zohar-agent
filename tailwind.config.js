/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./dashboard/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#030303",
        "esoteria-border": "rgba(255, 255, 255, 0.1)",
        "esoteria-glass": "rgba(255, 255, 255, 0.03)",
        brand: {
          blue: "#1793d1",
          emerald: "#10b981",
          amber: "#f59e0b",
          rose: "#f43f5e",
        }
      },
      fontFamily: {
        sans: ["Inter", "Geist", "ui-sans-serif", "system-ui"],
        mono: ["'Fira Code'", "monospace"],
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
}
