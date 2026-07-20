import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import { useMetricsSocket } from "../hooks/useWebSocket";
import { HardwareAPI } from "../api/endpoints";
import {
  Card,
  Spinner,
  EmptyState,
  RiskLabel,
  SeverityBadge,
} from "../components/ui";

// Colour a temperature value by severity band.
function tempColor(value, warn = 85, crit = 95) {
  if (value == null) return "text-slate-500";
  if (value >= crit) return "text-red-400";
  if (value >= warn) return "text-amber-400";
  return "text-emerald-400";
}

function LEVEL_STYLES(level) {
  return (
    {
      normal: "border-emerald-600/40 bg-emerald-600/10",
      warning: "border-amber-600/40 bg-amber-600/10",
      critical: "border-orange-600/50 bg-orange-600/10",
      emergency: "border-red-600/60 bg-red-600/15",
    }[level] || "border-ink-700"
  );
}

function SensorCard({ label, value, unit, warn, crit, sub }) {
  if (value == null) return null;
  return (
    <Card>
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`text-3xl font-bold ${tempColor(value, warn, crit)}`}>
        {typeof value === "number"
          ? value.toFixed(unit === "RPM" ? 0 : 1)
          : value}
        <span className="text-base text-slate-500 ml-1">{unit}</span>
      </div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </Card>
  );
}

function HealthGauge({ health }) {
  if (!health) return <Spinner />;
  const data = [
    { name: "health", value: health.overall, fill: gaugeColor(health.overall) },
  ];
  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={180}>
        <RadialBarChart
          innerRadius="70%"
          outerRadius="100%"
          data={data}
          startAngle={210}
          endAngle={-30}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar
            dataKey="value"
            cornerRadius={8}
            background={{ fill: "#1b2740" }}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="-mt-24 text-center">
        <div className="text-4xl font-bold text-slate-50">
          {health.overall.toFixed(0)}
        </div>
        <div className="text-xs uppercase tracking-wide text-slate-400">
          {health.rating}
        </div>
      </div>
    </div>
  );
}

function gaugeColor(v) {
  if (v >= 90) return "#22c55e";
  if (v >= 75) return "#84cc16";
  if (v >= 60) return "#f59e0b";
  return "#ef4444";
}

function ForecastCard({ title, prediction }) {
  if (!prediction)
    return (
      <Card title={title}>
        <Spinner />
      </Card>
    );
  const data = [
    { label: "now", value: prediction.current_value },
    ...prediction.points.map((p) => ({
      label: `+${p.minutes_ahead}m`,
      value: p.value,
    })),
  ];
  return (
    <Card title={title}>
      <div className="flex items-center justify-between mb-1 text-sm">
        <span className="text-slate-400">
          {prediction.model_name} · {(prediction.confidence * 100).toFixed(0)}%
          conf.
        </span>
        <RiskLabel risk={prediction.risk} />
      </div>
      <p className="text-xs text-slate-400 mb-2">{prediction.message}</p>
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--ink-700))" />
          <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
          <YAxis
            stroke="#64748b"
            fontSize={11}
            domain={["auto", "auto"]}
            unit="°"
          />
          <Tooltip
            contentStyle={{
              background: "rgb(var(--ink-800))",
              border: "1px solid rgb(var(--ink-700))",
            }}
          />
          <ReferenceLine y={95} stroke="#ef4444" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="value"
            stroke="rgb(var(--brand-500))"
            strokeWidth={2}
            dot
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default function Hardware() {
  const { hardware, hardwareHistory, connected } = useMetricsSocket(40);
  const [overview, setOverview] = useState(null);
  const [history, setHistory] = useState([]);
  const [cpuPred, setCpuPred] = useState(null);
  const [ssdPred, setSsdPred] = useState(null);
  const [battPred, setBattPred] = useState(null);
  const [alerts, setAlerts] = useState([]);

  const refresh = () => {
    HardwareAPI.overview()
      .then(setOverview)
      .catch(() => {});
    HardwareAPI.history(180, 300)
      .then((res) =>
        setHistory(
          res.points.map((p) => ({
            time: new Date(p.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            cpu: p.cpu_package_temp,
            ssd: p.ssd_temp,
            battery: p.battery_temp,
            fan: p.fan_speed,
            freq: p.cpu_frequency,
          })),
        ),
      )
      .catch(() => {});
    HardwareAPI.predictions("cpu_package_temp", 10)
      .then(setCpuPred)
      .catch(() => {});
    HardwareAPI.predictions("ssd_temp", 10)
      .then(setSsdPred)
      .catch(() => {});
    HardwareAPI.predictions("battery_temp", 10)
      .then(setBattPred)
      .catch(() => {});
    HardwareAPI.alerts({ limit: 20 })
      .then(setAlerts)
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, []);

  // Prefer the live WebSocket snapshot; fall back to the REST overview.
  const hw = hardware || overview?.snapshot;
  const liveChart = hardwareHistory.map((h, i) => ({
    i,
    cpu: h.cpu_package_temp,
    gpu: h.gpu_temp,
    ssd: h.ssd_temp,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">
            Hardware Health & Thermal Intelligence
          </h1>
          <p className="text-sm text-slate-400">
            Live sensors · {connected ? "streaming" : "offline"} ·{" "}
            {hw?.source && <span>source: {hw.source}</span>}
          </p>
        </div>
        <button onClick={refresh} className="btn-primary">
          Refresh
        </button>
      </div>

      {!hw ? (
        <Card>
          <EmptyState>
            Reading hardware sensors… If nothing appears, this host may expose
            few sensors (common in virtual machines). Run on physical Linux
            hardware with <code>lm-sensors</code> installed for full coverage.
          </EmptyState>
        </Card>
      ) : (
        <>
          {/* Live sensor cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
            <SensorCard
              label="CPU Package"
              value={hw.cpu_package_temp}
              unit="°C"
              warn={85}
              crit={95}
              sub={
                hw.cpu_frequency_mhz
                  ? `${(hw.cpu_frequency_mhz / 1000).toFixed(2)} GHz`
                  : null
              }
            />
            <SensorCard
              label="GPU"
              value={hw.gpu_temp}
              unit="°C"
              warn={85}
              crit={95}
            />
            <SensorCard
              label="SSD / NVMe"
              value={hw.ssd_temp}
              unit="°C"
              warn={70}
              crit={80}
            />
            <SensorCard
              label="Motherboard"
              value={hw.motherboard_temp}
              unit="°C"
              warn={80}
              crit={90}
            />
            <SensorCard
              label="Battery Temp"
              value={hw.battery_temp}
              unit="°C"
              warn={45}
              crit={55}
            />
            <SensorCard
              label="Fan Speed"
              value={hw.fan_speed_rpm}
              unit="RPM"
              warn={9999}
              crit={99999}
              sub="cooling"
            />
            <SensorCard
              label="Battery Charge"
              value={hw.battery_percent}
              unit="%"
              warn={101}
              crit={101}
              sub={hw.battery_status || "charge level"}
            />
            <SensorCard
              label="Battery Health"
              value={hw.battery_health}
              unit="%"
              warn={-1}
              crit={-1}
              sub="capacity vs. design"
            />
            <SensorCard
              label="CPU Load"
              value={hw.cpu_utilization}
              unit="%"
              warn={101}
              crit={101}
            />
          </div>

          {/* Health score + AI explanations */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card title="Overall Hardware Health">
              <HealthGauge health={overview?.health} />
              <div className="space-y-2 mt-2">
                {overview?.health?.components?.map((c) => (
                  <div
                    key={c.name}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-slate-300">{c.name}</span>
                    <span className="text-slate-400">
                      <span className="text-slate-200 font-medium">
                        {c.score.toFixed(0)}
                      </span>{" "}
                      · {c.status}
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="AI Thermal Intelligence" className="lg:col-span-2">
              <div className="space-y-3">
                {overview?.explanations?.map((e, i) => (
                  <div
                    key={i}
                    className={`border rounded-lg p-3 ${LEVEL_STYLES(e.level)}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-100">
                        {e.title}
                      </span>
                      <span className="text-xs uppercase tracking-wide text-slate-400">
                        {e.level}
                      </span>
                    </div>
                    <p className="text-sm text-slate-300">{e.explanation}</p>
                  </div>
                ))}
                {overview?.throttling?.throttling && (
                  <div className="text-xs text-red-300">
                    ⚠ {overview.throttling.message}
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Live temperature stream */}
          <Card title="Live temperature stream (°C)">
            {liveChart.length < 2 ? (
              <EmptyState>Collecting live sensor data…</EmptyState>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={liveChart}>
                  <defs>
                    <linearGradient id="hg-cpu" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgb(var(--ink-700))"
                  />
                  <XAxis dataKey="i" hide />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    unit="°"
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgb(var(--ink-800))",
                      border: "1px solid rgb(var(--ink-700))",
                    }}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="cpu"
                    stroke="#ef4444"
                    fill="url(#hg-cpu)"
                    name="CPU °C"
                  />
                  {liveChart.some((d) => d.ssd != null) && (
                    <Area
                      type="monotone"
                      dataKey="ssd"
                      stroke="#f59e0b"
                      fillOpacity={0}
                      name="SSD °C"
                    />
                  )}
                  {liveChart.some((d) => d.gpu != null) && (
                    <Area
                      type="monotone"
                      dataKey="gpu"
                      stroke="#a855f7"
                      fillOpacity={0}
                      name="GPU °C"
                    />
                  )}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Predictive thermal analytics */}
          <div>
            <h2 className="text-lg font-semibold text-slate-50 mb-3">
              Predictive Thermal Analytics
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <ForecastCard
                title="CPU temperature (next 10 min)"
                prediction={cpuPred}
              />
              <ForecastCard
                title="SSD temperature (next 10 min)"
                prediction={ssdPred}
              />
              <ForecastCard
                title="Battery temperature (next 10 min)"
                prediction={battPred}
              />
            </div>
          </div>

          {/* Historical timelines */}
          <Timeline
            title="Temperature history (°C)"
            data={history}
            series={[
              { key: "cpu", color: "#ef4444", name: "CPU" },
              { key: "ssd", color: "#f59e0b", name: "SSD" },
              { key: "battery", color: "#22c55e", name: "Battery" },
            ]}
            unit="°"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Timeline
              title="Fan speed history (RPM)"
              data={history}
              series={[{ key: "fan", color: "#38bdf8", name: "Fan RPM" }]}
            />
            <Timeline
              title="CPU frequency history (MHz)"
              data={history}
              series={[{ key: "freq", color: "#a855f7", name: "MHz" }]}
            />
          </div>

          {/* Recommendations + alerts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Recommendations">
              <div className="space-y-3">
                {overview?.recommendations?.map((r, i) => (
                  <div
                    key={i}
                    className="border-b border-ink-700/60 pb-2 last:border-0"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-200 text-sm font-medium">
                        {r.issue}
                      </span>
                      <SeverityBadge severity={r.severity} />
                    </div>
                    <ul className="list-disc pl-5 text-xs text-slate-400 mt-1">
                      {r.actions.map((a, j) => (
                        <li key={j}>{a}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </Card>
            <Card title="Thermal alerts">
              {!alerts.length ? (
                <EmptyState>No thermal alerts.</EmptyState>
              ) : (
                <ul className="space-y-2">
                  {alerts.map((a) => (
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
          </div>
        </>
      )}
    </div>
  );
}

function Timeline({ title, data, series, unit }) {
  const hasData = data.some((d) => series.some((s) => d[s.key] != null));
  return (
    <Card title={title}>
      {!hasData ? (
        <EmptyState>
          No history yet — leave the backend running to build timelines.
        </EmptyState>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--ink-700))" />
            <XAxis
              dataKey="time"
              stroke="#64748b"
              fontSize={11}
              minTickGap={40}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              unit={unit || ""}
              domain={["auto", "auto"]}
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
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
