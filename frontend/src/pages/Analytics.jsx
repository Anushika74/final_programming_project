import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { MetricsAPI } from "../api/endpoints";
import { Card, Spinner, EmptyState } from "../components/ui";

const RANGES = [
  { label: "15m", minutes: 15 },
  { label: "1h", minutes: 60 },
  { label: "6h", minutes: 360 },
  { label: "24h", minutes: 1440 },
  { label: "7d", minutes: 10080 },
];

export default function Analytics() {
  const [minutes, setMinutes] = useState(60);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    MetricsAPI.trends(minutes, 80)
      .then((res) => {
        setData(
          res.points.map((p) => ({
            time: new Date(p.bucket).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            cpu: p.cpu_avg,
            memory: p.memory_avg,
            disk: p.disk_avg,
            network: Math.round(p.network_avg / 1024),
          })),
        );
      })
      .finally(() => setLoading(false));
  }, [minutes]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-50">
          Historical Analytics
        </h1>
        <div className="flex gap-1 bg-ink-800 rounded-lg p-1">
          {RANGES.map((r) => (
            <button
              key={r.minutes}
              onClick={() => setMinutes(r.minutes)}
              className={`px-3 py-1 rounded-md text-sm ${
                minutes === r.minutes
                  ? "bg-brand-600 text-white"
                  : "text-slate-400 hover:text-slate-100"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Spinner />
      ) : !data.length ? (
        <Card>
          <EmptyState>
            No historical data yet. Metrics are persisted every minute — leave
            the backend running to build up trends.
          </EmptyState>
        </Card>
      ) : (
        <>
          <TrendChart
            title="CPU & Memory trend (%)"
            data={data}
            series={[
              { key: "cpu", color: "rgb(var(--brand-500))", name: "CPU %" },
              { key: "memory", color: "#22c55e", name: "Memory %" },
            ]}
            domain={[0, 100]}
          />
          <TrendChart
            title="Disk usage trend (%)"
            data={data}
            series={[{ key: "disk", color: "#f59e0b", name: "Disk %" }]}
            domain={[0, 100]}
          />
          <TrendChart
            title="Network throughput (KB/s)"
            data={data}
            series={[
              { key: "network", color: "#a855f7", name: "Network KB/s" },
            ]}
          />
        </>
      )}
    </div>
  );
}

function TrendChart({ title, data, series, domain }) {
  return (
    <Card title={title}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--ink-700))" />
          <XAxis
            dataKey="time"
            stroke="#64748b"
            fontSize={11}
            minTickGap={40}
          />
          <YAxis
            domain={domain || ["auto", "auto"]}
            stroke="#64748b"
            fontSize={11}
          />
          <Tooltip
            contentStyle={{
              background: "rgb(var(--ink-800))",
              border: "1px solid rgb(var(--ink-700))",
            }}
          />
          <Legend />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              name={s.name}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
