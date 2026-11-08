import { useCallback, useState } from "react";
import { supabase } from "@/shared/lib";

export type PasswordMode = "sign-in" | "sign-up";

/** Email + password sign-in (and one-time account creation) against Supabase
 *  Auth. Exists alongside Google sign-in because Google only redirects back to
 *  `localhost` or a public domain — so on a phone reaching this app by its LAN
 *  IP, password sign-in is the way in. The session lands in the same
 *  `AuthProvider` either way. */
export function usePasswordLogin() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (mode: PasswordMode, email: string, password: string) => {
    setBusy(true);
    setError(null);
    try {
      const { error: authError } =
        mode === "sign-in"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });
      if (authError) setError(authError.message);
    } finally {
      setBusy(false);
    }
  }, []);

  return { submit, busy, error };
}
