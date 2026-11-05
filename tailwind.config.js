/**
 * Tailwind for the welfare system. Build with `npm run build:css`; the output
 * (app/static/css/app.css) is committed, so the running app never needs Node.
 *
 * `brand` follows each group's colour: layouts set --brand-rgb per request.
 */
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
    './app/**/*.py',
  ],
  // Component variants whose names are built in templates ({{ tone }}, {{ category }})
  safelist: [
    { pattern: /^(stat-card__icon|badge|btn|flash|role-badge|status-dot|download-card)--/ },
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: 'rgb(var(--brand-rgb) / <alpha-value>)',
          dark: 'rgb(var(--brand-dark-rgb) / <alpha-value>)',
          pale: 'rgb(var(--brand-rgb) / 0.12)',
        },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
