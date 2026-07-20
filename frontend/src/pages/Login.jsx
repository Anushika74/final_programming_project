import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AuthAPI } from "../api/endpoints";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) navigate("/");

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await AuthAPI.register({
          username: form.username,
          email: form.email,
          password: form.password,
        });
      }
      await login(form.username, form.password);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card p-8 w-full max-w-md">
        <div className="text-center mb-6">
          <div className="text-3xl font-bold">
            <span className="text-slate-50">System</span>
            <span className="text-gradient">IQ</span>
          </div>
          <p className="text-sm text-lavender-glow/70 mt-1">
            ✦ AI-Powered System Monitoring & Optimization
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Username</label>
            <input
              className="input"
              value={form.username}
              onChange={update("username")}
              required
            />
          </div>
          {mode === "register" && (
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
          )}
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

          {error && <div className="text-sm text-red-400">{error}</div>}

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        <div className="text-center mt-4 text-sm text-slate-400">
          {mode === "login" ? (
            <button
              onClick={() => setMode("register")}
              className="hover:text-brand-400"
            >
              Need an account? Register
            </button>
          ) : (
            <button
              onClick={() => setMode("login")}
              className="hover:text-brand-400"
            >
              Already have an account? Sign in
            </button>
          )}
        </div>

        <p className="text-xs text-slate-600 text-center mt-6">
          Default admin: <code>admin / admin123</code>
        </p>
      </div>
    </div>
  );
}
