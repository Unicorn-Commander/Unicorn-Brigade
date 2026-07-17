/** @type {import('tailwindcss').Config} */
export default {
  // Class strategy so a future light theme can flip on `.dark` / `[data-theme]`.
  // Dark stays the default look (tokens below resolve to the dark palette on :root).
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  // Categorical stat-tile colors are built dynamically (`bg-${color}-500/20`,
  // `text-${color}-400`) from bare color names in domain/relationship maps, so
  // Tailwind can't see them by scanning. Safelisted here so the purple→unicorn
  // accent codemod (which removes the literal purple/pink classes) can't strip
  // these data-viz categorical colors out of the build.
  safelist: [
    'bg-purple-500/20', 'text-purple-400',
    'bg-pink-500/20', 'text-pink-400',
    'bg-indigo-500/20', 'text-indigo-400',
  ],
  theme: {
    extend: {
      colors: {
        // The one accent scale — brand mark, active nav, primary CTAs.
        unicorn: {
          50: '#fdf2f8',
          100: '#fce7f3',
          200: '#fbcfe8',
          300: '#f9a8d4',
          400: '#f472b6',
          500: '#ec4899',
          600: '#db2777',
          700: '#be185d',
          800: '#9d174d',
          900: '#831843',
          950: '#500724',
        },
        // Semantic design tokens — wired to the CSS vars in index.css so the
        // whole UI can be re-themed from one place. They resolve to the dark
        // slate palette on :root and flip to light on [data-theme="light"]
        // (bg ≈ slate-950/100, surface+card ≈ slate-900/white, elevated ≈
        // slate-800/200, border ≈ slate-700/300, fg ≈ slate-50/900, muted ≈
        // slate-400/600, accent = unicorn-500/600).
        bg: 'hsl(var(--bg) / <alpha-value>)',
        surface: 'hsl(var(--surface) / <alpha-value>)',
        card: 'hsl(var(--card) / <alpha-value>)',
        elevated: 'hsl(var(--elevated) / <alpha-value>)',
        border: 'hsl(var(--border) / <alpha-value>)',
        fg: 'hsl(var(--fg) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        accent: 'hsl(var(--accent) / <alpha-value>)',
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-ring-delayed': 'pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) 0.3s infinite',
        'audio-bar': 'audio-bar 0.5s ease-in-out infinite alternate',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.5' },
          '100%': { transform: 'scale(1.5)', opacity: '0' },
        },
        'audio-bar': {
          '0%': { height: '8px' },
          '100%': { height: '24px' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
