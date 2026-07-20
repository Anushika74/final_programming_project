import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  Thermometer,
  BatteryCharging,
  Bot,
  Zap,
  FileText,
  Bell,
  Lightbulb,
  Sparkles,
} from "lucide-react";
import { useMetricsSocket } from "../hooks/useWebSocket";
import { DashboardAPI, HardwareAPI } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import {
  Card,
  ProgressBar,
  SeverityBadge,
  EmptyState,
  AnimatedNumber,
  Skeleton,
} from "../components/ui";

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function HealthRing({ score }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score ?? 0));
  const stroke = pct >= 85 ? "#10b981" : pct >= 65 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative grid place-items-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle
          cx="70"
          cy="70"
          r={r}
          fill="none"
          stroke="rgb(var(--ink-700))"
          strokeWidth="10"
        />
        <circle
          cx="70"
          cy="70"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c - (pct / 100) * c}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-3xl font-bold text-slate-50">
          <AnimatedNumber value={pct} />
        </div>
        <div className="text-xs text-slate-500">health</div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  unit,
  Icon,
  percent,
  detail,
  decimals = 0,
  delay = 0,
}) {
  return (
    <Card hover delay={delay}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-slate-400">{label}</div>
          <div className="mt-1 text-2xl font-bold text-slate-50">
            {value == null ? (
              "—"
            ) : (
              <AnimatedNumber value={value} decimals={decimals} />
            )}
            <span className="ml-1 text-sm font-normal text-slate-500">
              {unit}
            </span>
          </div>
        </div>
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500/10 text-brand-400">
          <Icon size={20} />
        </div>
      </div>
      {percent != null && (
        <div className="mt-3">
          <ProgressBar value={percent} />
        </div>
      )}
      {detail && <div className="mt-2 text-xs text-slate-500">{detail}</div>}
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { metrics, hardware, history, connected } = useMetricsSocket(40);
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const load = () => {
      DashboardAPI.summary()
        .then(setSummary)
        .catch(() => {});
      HardwareAPI.healthScore()
        .then(setHealth)
        .catch(() => setHealth(null));
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const m = metrics || summary?.metrics;
  const chartData = history.map((h, i) => ({
    i,
    cpu: h.cpu_usage,
    memory: h.memory_usage,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">
            {greeting()},{" "}
            <span className="text-gradient">{user?.username}</span>
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-slate-400">
            <Sparkles size={14} className="text-brand-400" />
            Your AI system platform is{" "}
            {connected ? "monitoring in real time" : "reconnecting…"}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/assistant" className="btn-primary">
            <Bot size={16} /> Ask AI
          </Link>
          <Link to="/settings" className="btn-ghost">
            <Zap size={16} /> Optimize
          </Link>
          <Link to="/reports" className="btn-ghost">
            <FileText size={16} /> Reports
          </Link>
        </div>
      </div>

      {/* Health + quick stats */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <div className="flex items-center gap-4">
            <HealthRing score={health?.overall} />
            <div className="flex-1">
              <div className="text-sm text-slate-400">System Health</div>
              <div className="text-lg font-semibold capitalize text-slate-100">
                {health?.rating || "calculating…"}
              </div>
              <div className="mt-2 space-y-1">
                {(health?.components || []).slice(0, 3).map((c) => (
                  <div
                    key={c.name}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-slate-400">{c.name}</span>
                    <span className="text-slate-300">{c.score.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-4 lg:col-span-2">
          <StatCard
            label="CPU Usage"
            value={m?.cpu_usage}
            unit="%"
            Icon={Cpu}
            percent={m?.cpu_usage}
            detail={m ? `${m.cpu_count} cores · load ${m.load_avg_1m}` : ""}
            delay={0.05}
          />
          <StatCard
            label="Memory"
            value={m?.memory_usage}
            unit="%"
            Icon={MemoryStick}
            percent={m?.memory_usage}
            detail={
              m
                ? `${(m.memory_used_mb / 1024).toFixed(1)} / ${(m.memory_total_mb / 1024).toFixed(1)} GB`
                : ""
            }
            delay={0.1}
          />
          <StatCard
            label="Disk"
            value={m?.disk_usage}
            unit="%"
            Icon={HardDrive}
            percent={m?.disk_usage}
            detail={
              m
                ? `${m.disk_used_gb.toFixed(0)} / ${m.disk_total_gb.toFixed(0)} GB`
                : ""
            }
            delay={0.15}
          />
          <StatCard
            label="Network ↓"
            value={m ? m.network_recv / 1024 : null}
            unit="KB/s"
            Icon={Wifi}
            detail={m ? `↑ ${(m.network_sent / 1024).toFixed(0)} KB/s` : ""}
            delay={0.2}
          />
        </div>
      </div>

      {/* Temperature + battery */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="CPU Temp"
          value={hardware?.cpu_package_temp}
          unit="°C"
          Icon={Thermometer}
          decimals={0}
        />
        <StatCard
          label="Battery"
          value={hardware?.battery_health}
          unit="%"
          Icon={BatteryCharging}
          detail={hardware?.battery_status || ""}
        />
        <StatCard
          label="Uptime"
          value={m ? m.uptime_seconds / 3600 : null}
          unit="h"
          Icon={Zap}
          decimals={1}
        />
        <StatCard
          label="Fan"
          value={hardware?.fan_speed_rpm}
          unit="RPM"
          Icon={Wifi}
        />
      </div>

      {/* Live chart */}
      <Card title="Live resource usage (%)">
        {chartData.length < 2 ? (
          <div className="space-y-2">
            <Skeleton className="h-48 w-full" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="g-cpu" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="rgb(var(--brand-500))"
                    stopOpacity={0.5}
                  />
                  <stop
                    offset="95%"
                    stopColor="rgb(var(--brand-500))"
                    stopOpacity={0}
                  />
                </linearGradient>
                <linearGradient id="g-mem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgb(var(--ink-700))"
              />
              <XAxis dataKey="i" hide />
              <YAxis
                domain={[0, 100]}
                stroke="rgb(var(--slate-500))"
                fontSize={11}
              />
              <Tooltip
                contentStyle={{
                  background: "rgb(var(--ink-800))",
                  border: "1px solid rgb(var(--ink-700))",
                  borderRadius: 12,
                  color: "rgb(var(--slate-100))",
                }}
              />
              <Area
                type="monotone"
                dataKey="cpu"
                stroke="rgb(var(--brand-500))"
                fill="url(#g-cpu)"
                name="CPU %"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="memory"
                stroke="#22d3ee"
                fill="url(#g-mem)"
                name="Memory %"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Alerts + recommendations */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Active alerts">
          {!summary?.active_alerts?.length ? (
            <EmptyState icon={Bell} title="All clear">
              No active alerts — your system is healthy.
            </EmptyState>
          ) : (
            <ul className="space-y-2">
              {summary.active_alerts.map((a) => (
                <li
                  key={a.id}
                  className="flex items-start justify-between gap-3 text-sm"
                >
                  <span className="text-slate-300">{a.message}</span>
                  <SeverityBadge severity={a.severity} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="AI recommendations">
          {!summary?.recommendations?.length ? (
            <EmptyState icon={Lightbulb} title="Nothing to suggest">
              No recommendations right now. The AI will surface insights here.
            </EmptyState>
          ) : (
            <ul className="space-y-3">
              {summary.recommendations.map((r) => (
                <li key={r.id} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-200">
                      {r.title}
                    </span>
                    <SeverityBadge severity={r.severity} />
                  </div>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {r.recommendation}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Top consumers */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Top CPU consumers">
          <ProcessMiniTable rows={summary?.top_cpu} metric="cpu_usage" />
        </Card>
        <Card title="Top memory consumers">
          <ProcessMiniTable rows={summary?.top_memory} metric="memory_usage" />
        </Card>
      </div>
    </div>
  );
}

function ProcessMiniTable({ rows, metric }) {
  if (!rows?.length)
    return (
      <EmptyState title="No data">Process data will appear here.</EmptyState>
    );
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((p) => (
          <tr key={p.pid} className="border-b border-ink-700/60 last:border-0">
            <td className="py-1.5 text-slate-300">{p.name}</td>
            <td className="py-1.5 pr-3 text-right text-slate-500">
              PID {p.pid}
            </td>
            <td className="w-16 py-1.5 text-right text-slate-200">
              {p[metric].toFixed(1)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
