import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Inbox } from "lucide-react";

// ---- Card (animated, glassmorphic) ----
export function Card({
  title,
  action,
  children,
  className = "",
  hover = false,
  delay = 0,
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: "easeOut" }}
      className={`card ${hover ? "card-hover" : ""} p-4 ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
          )}
          {action}
        </div>
      )}
      {children}
    </motion.div>
  );
}

// ---- Severity / risk badges ----
const SEVERITY_STYLES = {
  info: "bg-slate-500/20 text-slate-300",
  low: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
};

export function SeverityBadge({ severity }) {
  const cls = SEVERITY_STYLES[severity] || SEVERITY_STYLES.info;
  return <span className={`badge ${cls}`}>{severity}</span>;
}

const RISK_STYLES = {
  low: "text-emerald-400",
  medium: "text-amber-400",
  high: "text-red-400",
};

export function RiskLabel({ risk }) {
  return (
    <span className={`font-semibold ${RISK_STYLES[risk] || "text-slate-300"}`}>
      {risk?.toUpperCase()}
    </span>
  );
}

// ---- Progress bar ----
export function ProgressBar({ value, max = 100, tone }) {
  const pct = Math.min(100, (value / max) * 100);
  const color =
    tone ||
    (pct >= 90 ? "bg-red-500" : pct >= 75 ? "bg-amber-500" : "bg-brand-500");
  return (
    <div className="w-full h-2 rounded-full bg-ink-900/70 overflow-hidden">
      <motion.div
        className={`h-full ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      />
    </div>
  );
}

// ---- Animated number counter (requestAnimationFrame, no deps) ----
export function AnimatedNumber({ value, decimals = 0, suffix = "" }) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  useEffect(() => {
    const from = fromRef.current;
    const to = Number(value) || 0;
    const duration = 600;
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return (
    <span>
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

// ---- Loading states ----
export function Spinner({ label = "Loading…" }) {
  return <div className="text-sm text-slate-400 py-6 text-center">{label}</div>;
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

export function CardSkeleton({ lines = 3 }) {
  return (
    <div className="card p-4 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
    </div>
  );
}

// ---- Empty state (icon + message + optional CTA) ----
export function EmptyState({ icon: Icon = Inbox, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-4">
      <div className="mb-3 grid place-items-center h-12 w-12 rounded-2xl bg-brand-500/10 text-brand-400">
        <Icon size={22} />
      </div>
      {title && <p className="text-sm font-medium text-slate-200">{title}</p>}
      {children && (
        <p className="text-sm text-slate-500 mt-1 max-w-sm">{children}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function humanBytes(bytes) {
  if (bytes == null) return "-";
  let v = bytes;
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (v < 1024 || unit === "TB") return `${v.toFixed(1)} ${unit}`;
    v /= 1024;
  }
  return `${v.toFixed(1)} TB`;
}
