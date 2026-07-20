import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, Lock, CheckCircle2 } from "lucide-react";
import { AlertsAPI } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import { Card, EmptyState, SeverityBadge, Spinner } from "../components/ui";

const POSTURE = [
  "JWT authentication with bcrypt password hashing",
  "Role-based access control (admin / user)",
  "Service bound to localhost by default",
  "Read-only file analyzer; confirmation-gated optimizations",
  "No telemetry — all data stays on this machine",
];

export default function Security() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    AlertsAPI.list({ limit: 50, only_unresolved: true })
      .then(setAlerts)
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false));
  }, []);

  const securityAlerts = alerts.filter(
    (a) => a.severity === "high" || a.severity === "critical",
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-50">Security Center</h1>
        <p className="text-sm text-slate-400">
          Posture, access and security-relevant events.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-emerald-500/10 text-emerald-400">
              <ShieldCheck size={24} />
            </div>
            <div>
              <div className="text-sm text-slate-400">Security posture</div>
              <div className="text-lg font-semibold text-slate-100">
                Hardened
              </div>
            </div>
          </div>
          <ul className="mt-4 space-y-2">
            {POSTURE.map((p) => (
              <li
                key={p}
                className="flex items-start gap-2 text-sm text-slate-300"
              >
                <CheckCircle2
                  size={16}
                  className="mt-0.5 shrink-0 text-emerald-400"
                />
                {p}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Session" className="lg:col-span-1">
          <div className="space-y-3 text-sm">
            <Row icon={Lock} label="Signed in as" value={user?.username} />
            <Row icon={ShieldCheck} label="Role" value={user?.role} />
            <Row
              icon={CheckCircle2}
              label="Account status"
              value={user?.is_active ? "active" : "inactive"}
            />
          </div>
        </Card>

        <Card title="Security events" className="lg:col-span-1">
          {loading ? (
            <Spinner />
          ) : !securityAlerts.length ? (
            <EmptyState icon={ShieldCheck} title="No security events">
              No high-severity events detected.
            </EmptyState>
          ) : (
            <ul className="space-y-2">
              {securityAlerts.map((a) => (
                <li
                  key={a.id}
                  className="flex items-start justify-between gap-2 text-sm"
                >
                  <span className="flex items-start gap-2 text-slate-300">
                    <ShieldAlert
                      size={15}
                      className="mt-0.5 shrink-0 text-red-400"
                    />
                    {a.message}
                  </span>
                  <SeverityBadge severity={a.severity} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-slate-400">
        <Icon size={15} /> {label}
      </span>
      <span className="capitalize text-slate-200">{value}</span>
    </div>
  );
}
