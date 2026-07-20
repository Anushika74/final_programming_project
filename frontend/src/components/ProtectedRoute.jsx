import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Guards routes: requires authentication, and optionally an admin role.
export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, isAdmin } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;
  return children;
}
