import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Bot,
  Activity,
  HardDrive,
  Brain,
  Cpu,
  FolderSearch,
  ScrollText,
  Bell,
  FileText,
  ShieldCheck,
  Settings as SettingsIcon,
  Users,
  ChevronLeft,
  Menu,
  X,
  LogOut,
  Gauge,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useMetricsSocket } from "../hooks/useWebSocket";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard, end: true },
  { to: "/assistant", label: "AI Assistant", Icon: Bot },
  { to: "/analytics", label: "System Monitoring", Icon: Activity },
  { to: "/hardware", label: "Hardware Health", Icon: HardDrive },
  { to: "/predictions", label: "Prediction Center", Icon: Brain },
  { to: "/processes", label: "Process Explorer", Icon: Cpu },
  { to: "/files", label: "File Intelligence", Icon: FolderSearch },
  { to: "/logs", label: "Log Intelligence", Icon: ScrollText },
  { to: "/alerts", label: "Alerts", Icon: Bell },
  { to: "/reports", label: "Reports", Icon: FileText },
  { to: "/security", label: "Security", Icon: ShieldCheck },
  { to: "/settings", label: "Settings", Icon: SettingsIcon },
];

function SidebarContent({ collapsed, onNavigate }) {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const { connected } = useMetricsSocket(1);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const linkClass = ({ isActive }) =>
    `nav-link group relative ${
      isActive
        ? "bg-brand-600/90 text-white shadow-glow"
        : "text-slate-400 hover:text-slate-100 hover:bg-ink-700/60"
    }`;

  const items = isAdmin
    ? [...NAV, { to: "/users", label: "User Management", Icon: Users }]
    : NAV;

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div
        className={`flex items-center gap-2 px-4 py-5 ${collapsed ? "justify-center px-0" : ""}`}
      >
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-glow">
          <Gauge size={20} />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-lg font-bold">
              <span className="text-slate-50">System</span>
              <span className="text-gradient">IQ</span>
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              AI System Platform
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-2">
        {items.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={linkClass}
            title={collapsed ? label : undefined}
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-ink-700/70 p-3 space-y-3">
        <div
          className={`flex items-center gap-2 text-xs ${collapsed ? "justify-center" : ""}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-red-400"}`}
          />
          {!collapsed && (
            <span className="text-slate-400">
              {connected ? "Live" : "Reconnecting…"}
            </span>
          )}
        </div>

        {!collapsed && <ThemeToggle compact />}

        <div
          className={`flex items-center gap-2 ${collapsed ? "justify-center" : ""}`}
        >
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink-700 text-xs font-semibold text-slate-200 uppercase">
            {user?.username?.slice(0, 2)}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-slate-200">
                {user?.username}
              </div>
              <div className="text-xs capitalize text-slate-500">
                {user?.role}
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            title="Log out"
            className="rounded-lg p-2 text-slate-400 hover:bg-ink-700 hover:text-red-300"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("systemiq_sidebar_collapsed") === "1",
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      localStorage.setItem("systemiq_sidebar_collapsed", c ? "0" : "1");
      return !c;
    });
  };

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <motion.aside
        animate={{ width: collapsed ? 80 : 256 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="glass fixed inset-y-0 left-0 z-30 hidden border-r border-ink-700/70 md:block"
      >
        <SidebarContent collapsed={collapsed} />
        <button
          onClick={toggleCollapsed}
          aria-label="Toggle sidebar"
          className="absolute -right-3 top-20 grid h-6 w-6 place-items-center rounded-full border border-ink-700 bg-ink-800 text-slate-300 shadow hover:text-brand-400"
        >
          <ChevronLeft
            size={14}
            className={`transition-transform ${collapsed ? "rotate-180" : ""}`}
          />
        </button>
      </motion.aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="glass fixed inset-y-0 left-0 z-50 w-64 border-r border-ink-700/70 md:hidden"
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-ink-700"
                aria-label="Close menu"
              >
                <X size={18} />
              </button>
              <SidebarContent
                collapsed={false}
                onNavigate={() => setMobileOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div
        className={`transition-all duration-300 ${collapsed ? "md:pl-20" : "md:pl-64"}`}
      >
        {/* Mobile top bar */}
        <div className="glass sticky top-0 z-20 flex items-center justify-between border-b border-ink-700/70 px-4 py-3 md:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-lg p-2 text-slate-300 hover:bg-ink-700"
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          <div className="text-base font-bold">
            <span className="text-slate-50">System</span>
            <span className="text-gradient">IQ</span>
          </div>
          <ThemeToggle compact />
        </div>

        <main className="mx-auto max-w-7xl p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
