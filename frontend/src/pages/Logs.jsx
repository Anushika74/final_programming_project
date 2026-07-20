import { useState } from "react";
import { LogsAPI } from "../api/endpoints";
import { Card, Spinner, EmptyState, SeverityBadge } from "../components/ui";

const SAMPLE = `Jun 21 09:14:02 host systemd[1]: Started Daily apt download activities.
Jun 21 09:15:31 host kernel: Out of memory: Killed process 4821 (chrome)
Jun 21 09:16:10 host sshd[2210]: Failed password for invalid user admin from 10.0.0.5
Jun 21 09:17:45 host NetworkManager[812]: device eth0: link disconnected
Jun 21 09:18:02 host systemd[1]: nginx.service: Failed with result 'exit-code'.`;

export default function Logs() {
  const [content, setContent] = useState("");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await LogsAPI.analyze(content, "manual");
      setSummary(res);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to analyze logs. Please try again.";
      setError(typeof detail === "string" ? detail : "Failed to analyze logs.");
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setContent("");
    setSummary(null);
    setError(null);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-50">Log Analyzer</h1>

      <Card
        title="Paste log content"
        action={
          <button className="btn-ghost" onClick={() => setContent(SAMPLE)}>
            Load sample
          </button>
        }
      >
        <textarea
          className="input font-mono text-xs h-40"
          placeholder="Paste system log lines here…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <div className="mt-3 flex items-center gap-2">
          <button
            className="btn-primary"
            onClick={analyze}
            disabled={loading || !content.trim()}
          >
            {loading ? "Analyzing…" : "Analyze logs"}
          </button>
          <button
            className="btn-ghost"
            onClick={clear}
            disabled={loading || (!content && !summary && !error)}
          >
            Clear
          </button>
        </div>
      </Card>

      {loading && <Spinner />}

      {error && (
        <Card>
          <p className="text-sm text-red-400">{error}</p>
        </Card>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(summary.by_severity).map(([sev, count]) => (
              <Card key={sev}>
                <div className="flex items-center justify-between">
                  <SeverityBadge severity={sev} />
                  <span className="text-xl font-bold text-slate-50">
                    {count}
                  </span>
                </div>
              </Card>
            ))}
          </div>

          <Card title={`Explained entries (${summary.total})`}>
            {!summary.entries.length ? (
              <EmptyState>Nothing notable to explain.</EmptyState>
            ) : (
              <div className="space-y-3">
                {summary.entries.map((e) => (
                  <div
                    key={e.id ?? e.raw_log}
                    className="border-b border-ink-700/60 pb-3 last:border-0"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <SeverityBadge severity={e.severity} />
                      <span className="text-xs text-slate-500">
                        {e.category}
                      </span>
                    </div>
                    <code className="block text-xs text-slate-400 break-all mb-1">
                      {e.raw_log}
                    </code>
                    <p className="text-sm text-slate-200">{e.explanation}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
