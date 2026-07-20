import { useEffect, useState } from "react";
import { UsersAPI } from "../api/endpoints";
import { useAuth } from "../context/AuthContext";
import { Card, Spinner, EmptyState } from "../components/ui";

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    role: "user",
  });
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    UsersAPI.list()
      .then(setUsers)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await UsersAPI.create(form);
      setForm({ username: "", email: "", password: "", role: "user" });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create user");
    }
  };

  const toggleRole = async (u) => {
    await UsersAPI.update(u.id, {
      role: u.role === "admin" ? "user" : "admin",
    });
    load();
  };

  const remove = async (u) => {
    if (window.confirm(`Delete user "${u.username}"?`)) {
      await UsersAPI.remove(u.id);
      load();
    }
  };

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-50">User Management</h1>

      <Card title="Create user">
        <form
          onSubmit={create}
          className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end"
        >
          <div>
            <label className="label">Username</label>
            <input
              className="input"
              value={form.username}
              onChange={update("username")}
              required
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input
              type="email"
              className="input"
              value={form.email}
              onChange={update("email")}
              required
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={update("password")}
              required
            />
          </div>
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={form.role}
              onChange={update("role")}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button className="btn-primary">Add user</button>
        </form>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </Card>

      <Card title="All users">
        {loading ? (
          <Spinner />
        ) : !users.length ? (
          <EmptyState>No users.</EmptyState>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-400 text-left">
              <tr className="border-b border-ink-700">
                <th className="py-2">ID</th>
                <th className="py-2">Username</th>
                <th className="py-2">Email</th>
                <th className="py-2">Role</th>
                <th className="py-2">Active</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-ink-700/50">
                  <td className="py-2 text-slate-500">{u.id}</td>
                  <td className="py-2 text-slate-200">{u.username}</td>
                  <td className="py-2 text-slate-400">{u.email}</td>
                  <td className="py-2 capitalize">{u.role}</td>
                  <td className="py-2">{u.is_active ? "yes" : "no"}</td>
                  <td className="py-2 text-right space-x-2">
                    <button
                      className="btn-ghost text-xs py-1"
                      onClick={() => toggleRole(u)}
                    >
                      Make {u.role === "admin" ? "user" : "admin"}
                    </button>
                    {u.id !== me?.id && (
                      <button
                        className="btn-ghost text-xs py-1 text-red-300"
                        onClick={() => remove(u)}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
