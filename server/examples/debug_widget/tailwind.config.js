/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      "./src/**/*.{ts,tsx,js,jsx}"
    ],
    theme: {
      extend: {},
    },
    plugins: [],
    corePlugins: {
      // If you want to avoid Tailwind's reset:
      preflight: false
    }
  }
  