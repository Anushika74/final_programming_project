import { useEffect, useState, useCallback } from "react";
import { AlertsAPI } from "../api/endpoints";
import { Card, Spinner, EmptyState, SeverityBadge } from "../components/ui";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [onlyOpen, setOnlyOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    AlertsAPI.list({ limit: 100, only_unresolved: onlyOpen })
      .then(setAlerts)
      .finally(() => setLoading(false));
  }, [onlyOpen]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const resolve = async (id) => {
    await AlertsAPI.resolve(id);
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-50">Alerts</h1>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={onlyOpen}
            onChange={(e) => setOnlyOpen(e.target.checked)}
          />
          Unresolved only
        </label>
      </div>

      <Card>
        {loading && !alerts.length ? (
          <Spinner />
        ) : !alerts.length ? (
          <EmptyState>
            No alerts. Thresholds are configured in Settings.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-left">
                <tr className="border-b border-ink-700">
                  <th className="py-2">Type</th>
                  <th className="py-2">Message</th>
                  <th className="py-2">Severity</th>
                  <th className="py-2 text-right">Value</th>
                  <th className="py-2">When</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} className="border-b border-ink-700/50">
                    <td className="py-2 uppercase text-slate-300">
                      {a.alert_type}
                    </td>
                    <td className="py-2 text-slate-300">{a.message}</td>
                    <td className="py-2">
                      <SeverityBadge severity={a.severity} />
                    </td>
                    <td className="py-2 text-right">{a.value.toFixed(0)}%</td>
                    <td className="py-2 text-slate-500">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td className="py-2 text-right">
                      {a.resolved ? (
                        <span className="text-emerald-400 text-xs">
                          resolved
                        </span>
                      ) : (
                        <button
                          onClick={() => resolve(a.id)}
                          className="btn-ghost text-xs py-1"
                        >
                          Resolve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
