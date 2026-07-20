import { useState } from "react";
import { FilesAPI } from "../api/endpoints";
import { Card, Spinner, EmptyState, humanBytes } from "../components/ui";

export default function Files() {
  const [path, setPath] = useState("");
  const [minMb, setMinMb] = useState(100);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const scan = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const res = await FilesAPI.scan({
        path,
        min_large_file_mb: Number(minMb),
        find_duplicates: true,
      });
      setResult(res);
    } catch (err) {
      setError(err.response?.data?.detail || "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-50">File Analyzer</h1>

      <Card>
        <form onSubmit={scan} className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[240px]">
            <label className="label">Directory path</label>
            <input
              className="input"
              placeholder="/home/user/Downloads"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              required
            />
          </div>
          <div className="w-40">
            <label className="label">Large file ≥ (MB)</label>
            <input
              type="number"
              className="input"
              value={minMb}
              onChange={(e) => setMinMb(e.target.value)}
            />
          </div>
          <button className="btn-primary" disabled={loading}>
            {loading ? "Scanning…" : "Scan"}
          </button>
        </form>
        {error && <p className="text-sm text-red-400 mt-3">{error}</p>}
      </Card>

      {loading && <Spinner label="Analyzing file system…" />}

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Stat
              label="Files scanned"
              value={result.scanned_files.toLocaleString()}
            />
            <Stat
              label="Total size"
              value={humanBytes(result.total_size_bytes)}
            />
            <Stat
              label="Reclaimable"
              value={humanBytes(result.reclaimable_bytes)}
            />
            <Stat
              label="Duplicate groups"
              value={result.duplicate_groups.length}
            />
          </div>

          <Card title="Recommendations">
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-300">
              {result.recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title={`Large files (${result.large_files.length})`}>
              <FileList items={result.large_files} />
            </Card>
            <Card
              title={`Temporary / junk files (${result.temp_files.length})`}
            >
              <FileList items={result.temp_files} />
            </Card>
          </div>

          <Card
            title={`Duplicate file groups (${result.duplicate_groups.length})`}
          >
            {!result.duplicate_groups.length ? (
              <EmptyState>No duplicates found.</EmptyState>
            ) : (
              <div className="space-y-3">
                {result.duplicate_groups.map((g) => (
                  <div
                    key={g.hash}
                    className="border border-ink-700 rounded-lg p-3"
                  >
                    <div className="text-sm text-slate-300 mb-1">
                      {g.files.length} copies · {humanBytes(g.size_bytes)} each
                      · wasting{" "}
                      <span className="text-amber-400">
                        {humanBytes(g.wasted_bytes)}
                      </span>
                    </div>
                    <ul className="text-xs text-slate-500 space-y-0.5">
                      {g.files.map((f) => (
                        <li key={f} className="truncate">
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {result.empty_folders.length > 0 && (
            <Card title={`Empty folders (${result.empty_folders.length})`}>
              <ul className="text-xs text-slate-500 space-y-0.5">
                {result.empty_folders.map((f) => (
                  <li key={f} className="truncate">
                    {f}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <Card>
      <div className="text-sm text-slate-400">{label}</div>
      <div className="text-xl font-bold text-slate-50">{value}</div>
    </Card>
  );
}

function FileList({ items }) {
  if (!items?.length) return <EmptyState>None found.</EmptyState>;
  return (
    <ul className="text-sm space-y-1">
      {items.map((f) => (
        <li key={f.path} className="flex justify-between gap-3">
          <span className="text-slate-400 truncate">{f.path}</span>
          <span className="text-slate-200 shrink-0">{f.size_human}</span>
        </li>
      ))}
    </ul>
  );
}
