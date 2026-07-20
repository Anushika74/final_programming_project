import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { PredictionsAPI } from "../api/endpoints";
import { Card, Spinner, RiskLabel } from "../components/ui";

function ForecastCard({ title, forecast }) {
  if (!forecast)
    return (
      <Card title={title}>
        <Spinner />
      </Card>
    );
  const chartData = [
    { label: "now", value: forecast.current_value },
    ...forecast.points.map((p) => ({
      label: `+${p.minutes_ahead}m`,
      value: p.value,
    })),
  ];
  return (
    <Card title={title}>
      <div className="flex items-center justify-between mb-2 text-sm">
        <span className="text-slate-400">
          Model: <span className="text-slate-200">{forecast.model_name}</span> ·
          confidence {(forecast.confidence * 100).toFixed(0)}%
        </span>
        <RiskLabel risk={forecast.risk} />
      </div>
      <p className="text-sm text-slate-300 mb-3">{forecast.message}</p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--ink-700))" />
          <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
          <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
          <Tooltip
            contentStyle={{
              background: "rgb(var(--ink-800))",
              border: "1px solid rgb(var(--ink-700))",
            }}
          />
          <ReferenceLine y={90} stroke="#ef4444" strokeDasharray="4 4" />
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

export default function Predictions() {
  const [cpu, setCpu] = useState(null);
  const [memory, setMemory] = useState(null);
  const [disk, setDisk] = useState(null);

  const refresh = () => {
    PredictionsAPI.forecast("cpu", 10)
      .then(setCpu)
      .catch(() => {});
    PredictionsAPI.forecast("memory", 10)
      .then(setMemory)
      .catch(() => {});
    PredictionsAPI.disk(7)
      .then(setDisk)
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">
            Prediction Center
          </h1>
          <p className="text-sm text-slate-400">
            ML forecasts (scikit-learn) with overload-risk indicators.
          </p>
        </div>
        <button onClick={refresh} className="btn-primary">
          Re-run forecasts
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ForecastCard title="CPU — next 10 minutes" forecast={cpu} />
        <ForecastCard title="Memory — next 10 minutes" forecast={memory} />
      </div>
      <ForecastCard title="Disk — 7 day projection" forecast={disk} />
    </div>
  );
}
