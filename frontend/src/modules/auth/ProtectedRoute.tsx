import { Navigate, Outlet } from "react-router";
import { LoadingDialog } from "@/shared/ui";
import { useSession } from "./shared/useSession";

export function ProtectedRoute() {
  const { status, booting } = useSession();

  if (booting) return <LoadingDialog />;
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}
