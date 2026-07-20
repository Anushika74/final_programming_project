import { useEffect, useState } from "react";
import { FileText, Printer, RefreshCw } from "lucide-react";
import { DashboardAPI, HardwareAPI } from "../api/endpoints";
import { Card, EmptyState, Spinner, SeverityBadge } from "../components/ui";

export default function Reports() {
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    Promise.all([
      DashboardAPI.summary().catch(() => null),
      HardwareAPI.healthScore().catch(() => null),
    ]).then(([s, h]) => {
      setSummary(s);
      setHealth(h);
      setLoading(false);
    });
  };

  useEffect(() => {
    load();
  }, []);

  const m = summary?.metrics;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">Reports</h1>
          <p className="text-sm text-slate-400">
            Executive system health report.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-ghost">
            <RefreshCw size={16} /> Refresh
          </button>
          <button onClick={() => window.print()} className="btn-primary">
            <Printer size={16} /> Print / Save PDF
          </button>
        </div>
      </div>

      {loading ? (
        <Spinner label="Compiling report…" />
      ) : !summary ? (
        <Card>
          <EmptyState icon={FileText} title="No report data yet">
            Start the monitoring service and collect some data, then return to
            generate a report.
          </EmptyState>
        </Card>
      ) : (
        <Card>
          <div className="space-y-5">
            <header className="border-b border-ink-700/60 pb-4">
              <div className="text-lg font-semibold text-slate-100">
                SystemIQ Health Report
              </div>
              <div className="text-xs text-slate-500">
                Generated {new Date().toLocaleString()}
              </div>
            </header>

            <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Metric
                label="Overall health"
                value={health ? `${health.overall.toFixed(0)}%` : "n/a"}
              />
              <Metric
                label="CPU"
                value={m ? `${m.cpu_usage.toFixed(0)}%` : "-"}
              />
              <Metric
                label="Memory"
                value={m ? `${m.memory_usage.toFixed(0)}%` : "-"}
              />
              <Metric
                label="Disk"
                value={m ? `${m.disk_usage.toFixed(0)}%` : "-"}
              />
            </section>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-200">
                Active alerts
              </h3>
              {!summary.active_alerts?.length ? (
                <p className="text-sm text-slate-500">None — system healthy.</p>
              ) : (
                <ul className="space-y-1">
                  {summary.active_alerts.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-slate-300">{a.message}</span>
                      <SeverityBadge severity={a.severity} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-200">
                Recommendations
              </h3>
              {!summary.recommendations?.length ? (
                <p className="text-sm text-slate-500">No recommendations.</p>
              ) : (
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
                  {summary.recommendations.map((r) => (
                    <li key={r.id}>
                      {r.title} — {r.recommendation}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </Card>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-ink-700/60 bg-ink-900/40 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-50">{value}</div>
    </div>
  );
}
