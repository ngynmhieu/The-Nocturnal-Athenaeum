import { supabase } from "@/shared/lib";

export function useLogin() {
  const login = () =>
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });

  return { login };
}
