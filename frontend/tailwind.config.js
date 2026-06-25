/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary:  'var(--bg-tertiary)',
          hover:     'var(--bg-hover)',
        },
        border: {
          subtle:  'var(--border-subtle)',
          default: 'var(--border-default)',
          strong:  'var(--border-strong)',
        },
        fg: {
          primary:   'var(--fg-primary)',
          secondary: 'var(--fg-secondary)',
          muted:     'var(--fg-muted)',
          subtle:    'var(--fg-subtle)',
        },
        status: {
          success:   '#10B981',
          successBg: 'rgba(16, 185, 129, 0.1)',
          danger:    '#EF4444',
          dangerBg:  'rgba(239, 68, 68, 0.1)',
          warning:   '#F59E0B',
          warningBg: 'rgba(245, 158, 11, 0.1)',
          info:      '#3B82F6',
          infoBg:    'rgba(59, 130, 246, 0.1)',
        },
        brand: {
          primary:   '#6366F1',
          secondary: '#8B5CF6',
          tertiary:  '#06B6D4',
        },
        chart: {
          blue:    '#3B82F6',
          violet:  '#8B5CF6',
          cyan:    '#06B6D4',
          emerald: '#10B981',
          amber:   '#F59E0B',
          rose:    '#F43F5E',
          fuchsia: '#D946EF',
          teal:    '#14B8A6',
        },
        dark: {
          900: '#0A0E1A', 800: '#0F1623', 700: '#151D2D', 600: '#1C2538',
          500: '#293548', 400: '#3B4862', 300: '#64748B', 200: '#94A3B8', 100: '#CBD5E1',
        },
        accent: {
          blue: '#6366F1', purple: '#8B5CF6', cyan: '#06B6D4',
          emerald: '#10B981', orange: '#F59E0B', pink: '#F43F5E',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
      fontSize: { '2xs': ['0.6875rem', '0.875rem'] },
      animation: {
        'fade-in':    'fadeIn 0.3s ease-in-out',
        'slide-up':   'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer':    'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        shimmer: { '0%': { backgroundPosition: '-1000px 0' }, '100%': { backgroundPosition: '1000px 0' } },
      },
      boxShadow: {
        'glow-blue':    '0 0 20px rgba(99, 102, 241, 0.3)',
        'glow-emerald': '0 0 20px rgba(16, 185, 129, 0.3)',
        'glow-rose':    '0 0 20px rgba(244, 63, 94, 0.3)',
        'card':         '0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px -1px rgba(0, 0, 0, 0.2)',
        'card-hover':   '0 4px 12px 0 rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
      },
    },
  },
  plugins: [],
}
