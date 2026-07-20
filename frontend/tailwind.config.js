/** @type {import('tailwindcss').Config} */
// SystemIQ design system. Colours are driven by CSS variables so the whole app
// supports light / dark themes and a switchable accent colour without touching
// individual components:
//   - `ink.*`   = surfaces (page, cards, borders) — flips between themes
//   - `slate.*` = content/text — flips between themes
//   - `brand.*` = the accent (electric blue by default; user-switchable)
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Accent / brand — driven by CSS vars (Settings can switch the accent).
        brand: {
          50: v("--brand-50"),
          100: v("--brand-100"),
          200: v("--brand-200"),
          400: v("--brand-400"),
          500: v("--brand-500"),
          600: v("--brand-600"),
          700: v("--brand-700"),
        },
        // Surfaces — theme-aware.
        ink: {
          900: v("--ink-900"),
          800: v("--ink-800"),
          700: v("--ink-700"),
          600: v("--ink-600"),
        },
        // Content/text — theme-aware (overrides Tailwind's default slate).
        slate: {
          50: v("--slate-50"),
          100: v("--slate-100"),
          200: v("--slate-200"),
          300: v("--slate-300"),
          400: v("--slate-400"),
          500: v("--slate-500"),
          600: v("--slate-600"),
          700: v("--slate-700"),
          900: v("--slate-900"),
        },
        lavender: { glow: v("--brand-200") },
      },
      boxShadow: {
        glow: "0 0 24px -4px rgb(var(--brand-500) / 0.45)",
        card: "0 10px 30px -12px rgba(0,0,0,0.55)",
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.25rem" },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
