/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./public/index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          magenta: '#ef2cc1',
          orange: '#fc4c02',
          dark: '#010120',
          lavender: '#bdbbff',
        },
        surface: {
          light: '#ffffff',
          dark: '#010120',
          glass: 'rgba(255, 255, 255, 0.12)',
          glassDark: 'rgba(0, 0, 0, 0.08)',
        }
      },
      fontFamily: {
        primary: ['The Future', 'Arial', 'sans-serif'],
        mono: ['PP Neue Montreal Mono', 'Georgia', 'monospace'],
      },
      boxShadow: {
        card: '0px 4px 10px rgba(1, 1, 32, 0.1)',
        elevated: '0px 4px 10px rgba(1, 1, 32, 0.1)',
      },
      borderRadius: {
        sharp: '4px',
        comfortable: '8px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      letterSpacing: {
        tighter: '-0.05em',
        tight: '-0.025em',
        wide: '0.025em',
      },
    },
  },
  plugins: [],
}