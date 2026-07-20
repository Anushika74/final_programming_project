import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";

const ThemeContext = createContext(null);

const THEME_KEY = "systemiq_theme"; // "light" | "dark" | "system"
const ACCENT_KEY = "systemiq_accent"; // blue | indigo | cyan | emerald | violet

const ACCENTS = ["blue", "indigo", "cyan", "emerald", "violet"];

function systemPrefersDark() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function resolve(theme) {
  if (theme === "system") return systemPrefersDark() ? "dark" : "light";
  return theme;
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(
    () => localStorage.getItem(THEME_KEY) || "dark",
  );
  const [accent, setAccentState] = useState(
    () => localStorage.getItem(ACCENT_KEY) || "blue",
  );

  // Apply resolved theme + accent to <html>.
  const apply = useCallback((t, a) => {
    const root = document.documentElement;
    const resolved = resolve(t);
    root.classList.remove("light", "dark");
    root.classList.add(resolved);
    root.setAttribute("data-accent", a);
  }, []);

  useEffect(() => {
    apply(theme, accent);
  }, [theme, accent, apply]);

  // React to OS theme changes when in "system" mode.
  useEffect(() => {
    if (theme !== "system" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => apply("system", accent);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, [theme, accent, apply]);

  const setTheme = useCallback((t) => {
    setThemeState(t);
    localStorage.setItem(THEME_KEY, t);
  }, []);

  const setAccent = useCallback((a) => {
    setAccentState(a);
    localStorage.setItem(ACCENT_KEY, a);
  }, []);

  const value = {
    theme,
    accent,
    accents: ACCENTS,
    resolvedTheme: resolve(theme),
    setTheme,
    setAccent,
    toggle: () => setTheme(resolve(theme) === "dark" ? "light" : "dark"),
  };

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
