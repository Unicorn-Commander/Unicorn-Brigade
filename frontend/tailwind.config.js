/** @type {import('tailwindcss').Config} */
//
// Tailwind is wired to src/styles/tokens.css. Colours, radii, shadows, z-index,
// type scale and motion below are the ONLY values the app may use; the
// design-system ratchet (scripts/audit-design-system.mjs) counts raw palette
// classes, arbitrary sizes and off-token radii/shadows and fails if the count
// ever goes up. See docs/DESIGN-SYSTEM.md.
export default {
  // Class strategy: data-theme + the `dark` class are flipped by src/utils/theme.js.
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  // Categorical stat-tile colours are built dynamically from bare colour names
  // in domain maps, so Tailwind can't see them by scanning.
  safelist: [
    'bg-purple-500/20', 'text-purple-400',
    'bg-pink-500/20', 'text-pink-400',
    'bg-indigo-500/20', 'text-indigo-400',
  ],
  theme: {
    extend: {
      colors: {
        // ── Surfaces ────────────────────────────────────────────────────
        bg: 'hsl(var(--bg) / <alpha-value>)',
        surface: 'hsl(var(--surface) / <alpha-value>)',
        card: 'hsl(var(--card) / <alpha-value>)',
        elevated: 'hsl(var(--elevated) / <alpha-value>)',
        overlay: 'hsl(var(--overlay) / <alpha-value>)',
        // ── Edges ───────────────────────────────────────────────────────
        border: 'hsl(var(--border) / <alpha-value>)',
        'border-strong': 'hsl(var(--border-strong) / <alpha-value>)',
        // ── Text ────────────────────────────────────────────────────────
        fg: 'hsl(var(--fg) / <alpha-value>)',
        'fg-strong': 'hsl(var(--fg-strong) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        subtle: 'hsl(var(--subtle) / <alpha-value>)',
        // ── Brand ───────────────────────────────────────────────────────
        accent: 'hsl(var(--accent) / <alpha-value>)',
        'accent-fill': 'hsl(var(--accent-fill) / <alpha-value>)',
        'on-accent': 'hsl(var(--on-accent) / <alpha-value>)',
        // ── Status ──────────────────────────────────────────────────────
        ok: 'hsl(var(--ok) / <alpha-value>)',
        'ok-fill': 'hsl(var(--ok-fill) / <alpha-value>)',
        warn: 'hsl(var(--warn) / <alpha-value>)',
        'warn-fill': 'hsl(var(--warn-fill) / <alpha-value>)',
        'on-warn': 'hsl(var(--on-warn) / <alpha-value>)',
        danger: 'hsl(var(--danger) / <alpha-value>)',
        'danger-fill': 'hsl(var(--danger-fill) / <alpha-value>)',
        info: 'hsl(var(--info) / <alpha-value>)',
        'info-fill': 'hsl(var(--info-fill) / <alpha-value>)',
        live: 'hsl(var(--live) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
        // The brand magenta scale. Kept for the wordmark and gradients; UI
        // code uses the semantic tokens above (the ratchet counts raw uses).
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
      },
      // ── Type scale (size / line-height / tracking / weight) ───────────
      // 11px is the floor: nothing a person must read is smaller.
      fontSize: {
        micro: ['11px', { lineHeight: '16px', letterSpacing: '0.02em' }],
        caption: ['12px', { lineHeight: '16px' }],
        'body-sm': ['13px', { lineHeight: '18px' }],
        body: ['14px', { lineHeight: '20px' }],
        lead: ['16px', { lineHeight: '24px' }],
        heading: ['18px', { lineHeight: '26px', fontWeight: '600' }],
        title: ['22px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '600' }],
        display: ['28px', { lineHeight: '34px', letterSpacing: '-0.02em', fontWeight: '700' }],
        hero: ['40px', { lineHeight: '44px', letterSpacing: '-0.025em', fontWeight: '800' }],
      },
      fontFamily: {
        sans: [
          'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"',
          'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif',
        ],
        mono: ['ui-monospace', '"SF Mono"', 'Menlo', 'Consolas', '"Liberation Mono"', 'monospace'],
      },
      // ── Radius ramp ───────────────────────────────────────────────────
      borderRadius: {
        chip: '6px',
        control: '8px',
        card: '12px',
        pane: '16px',
      },
      // ── Elevation ─────────────────────────────────────────────────────
      boxShadow: {
        e1: 'var(--shadow-e1)',
        e2: 'var(--shadow-e2)',
        e3: 'var(--shadow-e3)',
        e4: 'var(--shadow-e4)',
      },
      // ── Stacking ──────────────────────────────────────────────────────
      zIndex: {
        raised: '10',
        sticky: '20',
        dock: '30',
        nav: '40',
        overlay: '50',
        modal: '60',
        popover: '70',
        toast: '80',
        tooltip: '90',
      },
      // ── Motion ────────────────────────────────────────────────────────
      transitionDuration: {
        fast: '120ms',
        base: '200ms',
        slow: '320ms',
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.2, 0, 0, 1)',
        emphasized: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      backgroundImage: {
        'gradient-brand': 'var(--gradient-brand)',
        'gradient-accent': 'var(--gradient-accent)',
      },
      minHeight: {
        touch: '44px',
      },
      minWidth: {
        touch: '44px',
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-ring-delayed': 'pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) 0.3s infinite',
        'audio-bar': 'audio-bar 0.5s ease-in-out infinite alternate',
        'fade-in': 'fade-in 200ms cubic-bezier(0.2, 0, 0, 1)',
        'slide-up': 'slide-up 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scale-in 160ms cubic-bezier(0.16, 1, 0.3, 1)',
        shimmer: 'shimmer 1.6s linear infinite',
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
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.97)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-600px 0' },
          '100%': { backgroundPosition: '600px 0' },
        },
      },
    },
  },
  plugins: [],
};
