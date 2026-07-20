import { useEffect, useState, useCallback } from "react";
import { ProcessesAPI } from "../api/endpoints";
import { Card, Spinner, EmptyState } from "../components/ui";

export default function Processes() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("cpu");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    ProcessesAPI.list({
      search: search || undefined,
      sort_by: sortBy,
      descending: true,
      limit: 100,
    })
      .then(setRows)
      .finally(() => setLoading(false));
  }, [search, sortBy]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const openDetail = (pid) => {
    ProcessesAPI.detail(pid)
      .then(setSelected)
      .catch(() => setSelected(null));
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-50">Process Explorer</h1>

      <Card>
        <div className="flex flex-wrap gap-3 items-end mb-4">
          <div className="flex-1 min-w-[200px]">
            <label className="label">Search</label>
            <input
              className="input"
              placeholder="Filter by process name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Sort by</label>
            <select
              className="input"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="cpu">CPU usage</option>
              <option value="memory">Memory usage</option>
              <option value="name">Name</option>
              <option value="pid">PID</option>
            </select>
          </div>
          <button onClick={load} className="btn-ghost">
            Refresh
          </button>
        </div>

        {loading && !rows.length ? (
          <Spinner />
        ) : !rows.length ? (
          <EmptyState>No processes match.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-400 text-left">
                <tr className="border-b border-ink-700">
                  <th className="py-2">Name</th>
                  <th className="py-2">PID</th>
                  <th className="py-2">User</th>
                  <th className="py-2 text-right">CPU %</th>
                  <th className="py-2 text-right">Mem %</th>
                  <th className="py-2 text-right">Mem (MB)</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.pid}
                    onClick={() => openDetail(p.pid)}
                    className="border-b border-ink-700/50 hover:bg-ink-700/40 cursor-pointer"
                  >
                    <td className="py-1.5 text-slate-200">{p.name}</td>
                    <td className="py-1.5 text-slate-400">{p.pid}</td>
                    <td className="py-1.5 text-slate-500">
                      {p.username || "-"}
                    </td>
                    <td className="py-1.5 text-right">
                      {p.cpu_usage.toFixed(1)}
                    </td>
                    <td className="py-1.5 text-right">
                      {p.memory_usage.toFixed(1)}
                    </td>
                    <td className="py-1.5 text-right">
                      {p.memory_mb.toFixed(0)}
                    </td>
                    <td className="py-1.5 text-slate-400">{p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selected && (
        <Card
          title={`Process detail — ${selected.name} (PID ${selected.pid})`}
          action={
            <button className="btn-ghost" onClick={() => setSelected(null)}>
              Close
            </button>
          }
        >
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <Detail label="CPU %" value={selected.cpu_usage.toFixed(1)} />
            <Detail label="Memory %" value={selected.memory_usage.toFixed(1)} />
            <Detail label="Memory MB" value={selected.memory_mb.toFixed(0)} />
            <Detail label="Threads" value={selected.num_threads} />
            <Detail label="Status" value={selected.status} />
            <Detail label="User" value={selected.username || "-"} />
            <Detail label="Nice" value={selected.nice ?? "-"} />
            <Detail
              label="Executable"
              value={selected.exe || "-"}
              className="col-span-2 truncate"
            />
          </div>
          {selected.cmdline?.length > 0 && (
            <div className="mt-3">
              <div className="label">Command line</div>
              <code className="block bg-ink-900 rounded-lg p-2 text-xs text-slate-300 break-all">
                {selected.cmdline.join(" ")}
              </code>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function Detail({ label, value, className = "" }) {
  return (
    <div className={className}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-slate-200">{value}</div>
    </div>
  );
}
