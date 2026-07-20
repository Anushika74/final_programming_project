import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "../context/ThemeContext";

const OPTIONS = [
  { key: "light", label: "Light", Icon: Sun },
  { key: "dark", label: "Dark", Icon: Moon },
  { key: "system", label: "System", Icon: Monitor },
];

/** Segmented light / dark / system theme switcher. */
export default function ThemeToggle({ compact = false }) {
  const { theme, setTheme } = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="inline-flex items-center gap-1 rounded-xl border border-ink-700 bg-ink-900/50 p-1"
    >
      {OPTIONS.map(({ key, label, Icon }) => {
        const active = theme === key;
        return (
          <button
            key={key}
            role="radio"
            aria-checked={active}
            title={label}
            onClick={() => setTheme(key)}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
              active
                ? "bg-brand-600 text-white shadow-glow"
                : "text-slate-400 hover:text-slate-200 hover:bg-ink-700/60"
            }`}
          >
            <Icon size={15} />
            {!compact && <span>{label}</span>}
          </button>
        );
      })}
    </div>
  );
}
