/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'deep-space': '#0B0E14',
        'electric-indigo': '#6366F1',
      },
      borderRadius: {
        'sm': '2px',
        'md': '4px',
        'lg': '12px',
      },
      backdropBlur: {
        'glass': '32px',
      }
    },
  },
  plugins: [],
}
