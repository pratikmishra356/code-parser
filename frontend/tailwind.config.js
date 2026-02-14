/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        surface: {
          50: '#ffffff',
          100: '#fafbfc',
          200: '#f5f7fa',
          300: '#e8ecf1',
          400: '#d1d9e3',
          500: '#a8b4c5',
          600: '#7d8fa3',
          700: '#5a6b7f',
          800: '#3d4859',
          900: '#252d3a',
          950: '#1a1f2a',
        },
        accent: {
          50: '#e6faf5',
          100: '#b3f0e0',
          200: '#80e6cb',
          300: '#4ddcb6',
          400: '#1ad2a1',
          500: '#10b386', // Primary vibrant teal-green
          600: '#0d8f6b',
          700: '#0a6b50',
          800: '#074735',
          900: '#04231a',
        },
        primary: {
          50: '#e6faf5',
          100: '#b3f0e0',
          200: '#80e6cb',
          300: '#4ddcb6',
          400: '#1ad2a1',
          500: '#10b386', // Primary vibrant teal-green
          600: '#0d8f6b',
          700: '#0a6b50',
        }
      }
    },
  },
  plugins: [],
}

