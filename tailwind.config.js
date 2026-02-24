/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#0a0c10',
          surface: 'rgba(255,255,255,0.03)',
          accent: '#00f0ff',
          yellow: '#ffc800',
          muted: 'rgba(255,255,255,0.5)',
        },
      },
      fontFamily: {
        outfit: ['Outfit', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
