import { useEffect, useState } from "react";
import { Palette } from "lucide-react";
import { OptimizationAPI, RecommendationsAPI } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Card, EmptyState, SeverityBadge } from "../components/ui";
import ThemeToggle from "../components/ThemeToggle";

const ACCENT_SWATCHES = {
  blue: "#3b82f6",
  indigo: "#6366f1",
  cyan: "#06b6d4",
  emerald: "#10b981",
  violet: "#8b5cf6",
};

export default function Settings() {
  const { user } = useAuth();
  const { accent, accents, setAccent } = useTheme();
  const [actions, setActions] = useState([]);
  const [recs, setRecs] = useState([]);
  const [output, setOutput] = useState(null);

  const loadRecs = () =>
    RecommendationsAPI.list({ limit: 50 })
      .then(setRecs)
      .catch(() => {});

  useEffect(() => {
    OptimizationAPI.actions()
      .then(setActions)
      .catch(() => {});
    loadRecs();
  }, []);

  const run = async (key, confirm) => {
    const res = await OptimizationAPI.execute(key, confirm, !confirm);
    setOutput(res);
  };

  const generate = async () => {
    await RecommendationsAPI.generate();
    loadRecs();
  };

  const acknowledge = async (id) => {
    await RecommendationsAPI.acknowledge(id);
    loadRecs();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-50">Settings</h1>

      <Card title="Appearance">
        <div className="space-y-5">
          <div>
            <div className="label">Theme</div>
            <ThemeToggle />
          </div>
          <div>
            <div className="label flex items-center gap-1.5">
              <Palette size={13} /> Accent colour
            </div>
            <div className="flex gap-2">
              {accents.map((a) => (
                <button
                  key={a}
                  onClick={() => setAccent(a)}
                  aria-label={a}
                  title={a}
                  className={`h-8 w-8 rounded-full border-2 transition-transform hover:scale-110 ${
                    accent === a
                      ? "border-slate-100 scale-110"
                      : "border-transparent"
                  }`}
                  style={{ backgroundColor: ACCENT_SWATCHES[a] }}
                />
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Profile">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <Info label="Username" value={user?.username} />
          <Info label="Email" value={user?.email} />
          <Info label="Role" value={user?.role} />
        </div>
      </Card>

      <Card
        title="Optimization actions"
        action={
          <span className="text-xs text-slate-500">
            Dry-run is safe; Apply requires confirmation
          </span>
        }
      >
        <div className="space-y-3">
          {actions.map((a) => (
            <div
              key={a.key}
              className="flex items-center justify-between gap-3 border-b border-ink-700/60 pb-3 last:border-0"
            >
              <div>
                <div className="text-slate-200 text-sm font-medium">
                  {a.title}{" "}
                  <span className="text-xs text-slate-500">
                    ({a.risk} risk)
                  </span>
                </div>
                <div className="text-xs text-slate-400">{a.description}</div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  className="btn-ghost text-xs py-1"
                  onClick={() => run(a.key, false)}
                >
                  Dry run
                </button>
                <button
                  className="btn-primary text-xs py-1"
                  onClick={() => {
                    if (
                      window.confirm(
                        `Apply "${a.title}"? This requires confirmation.`,
                      )
                    ) {
                      run(a.key, true);
                    }
                  }}
                >
                  Apply
                </button>
              </div>
            </div>
          ))}
        </div>
        {output && (
          <div className="mt-4 bg-ink-900 rounded-lg p-3 text-sm">
            <div className="text-slate-300">{output.message}</div>
            <div className="text-xs text-slate-500 mt-1">
              executed: {String(output.executed)} · dry_run:{" "}
              {String(output.dry_run)}
            </div>
          </div>
        )}
      </Card>

      <Card
        title="Recommendations"
        action={
          <button className="btn-primary text-xs py-1" onClick={generate}>
            Generate now
          </button>
        }
      >
        {!recs.length ? (
          <EmptyState>No recommendations.</EmptyState>
        ) : (
          <div className="space-y-3">
            {recs.map((r) => (
              <div
                key={r.id}
                className="flex items-start justify-between gap-3 border-b border-ink-700/60 pb-3 last:border-0"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-200 text-sm font-medium">
                      {r.title}
                    </span>
                    <SeverityBadge severity={r.severity} />
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {r.recommendation}
                  </p>
                </div>
                {!r.acknowledged && (
                  <button
                    className="btn-ghost text-xs py-1 shrink-0"
                    onClick={() => acknowledge(r.id)}
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-slate-200 capitalize">{value}</div>
    </div>
  );
}
