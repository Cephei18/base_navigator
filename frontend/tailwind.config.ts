import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          950: '#070b12',
          900: '#0b1019',
          850: '#101722',
          800: '#151d2a',
          700: '#202a3a'
        },
        ink: {
          50: '#f5f8fc',
          100: '#e7edf7',
          300: '#a8b4c7',
          500: '#6f7d92'
        },
        base: {
          400: '#6aa6ff',
          500: '#397cff',
          600: '#195ee8'
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'SFMono-Regular', 'monospace']
      },
      boxShadow: {
        terminal: '0 24px 80px rgba(0, 0, 0, 0.32)'
      }
    }
  },
  plugins: []
}

export default config
