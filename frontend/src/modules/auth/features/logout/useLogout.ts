import { supabase } from "@/shared/lib";

export function useLogout() {
  const logout = () => supabase.auth.signOut();
  return { logout };
}
