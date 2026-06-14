import { Navigate, Outlet } from "react-router";
import { useSession } from "./shared/useSession";

export function ProtectedRoute() {
  const { status } = useSession();

  if (status === "loading") return null;
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}
