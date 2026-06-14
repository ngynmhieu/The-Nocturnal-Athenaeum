import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/shared/lib";
import { AuthContext } from "./authContext";
import type { AuthStatus } from "./authContext";
import type { AuthUser } from "../entities";
import { syncProfile } from "./authApi";

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [profileSynced, setProfileSynced] = useState(false);
  const syncedRef = useRef<string | null>(null);

  useEffect(() => {
    supabase.auth.getClaims().then(({ error }) => {
      if (error) {
        setSession(null);
        setStatus("anonymous");
      }
    });

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setStatus(data.session ? "authenticated" : "anonymous");
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setStatus(newSession ? "authenticated" : "anonymous");

      if (!newSession) {
        setUser(null);
        setProfileSynced(false);
        syncedRef.current = null;
        return;
      }

      if (syncedRef.current !== newSession.user.id) {
        syncedRef.current = newSession.user.id;
        syncProfile(newSession.access_token)
          .then((profile) => { if (profile) setUser(profile); })
          .catch(() => {})
          .finally(() => setProfileSynced(true));
      }
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const booting =
    status === "loading" || (status === "authenticated" && !profileSynced);

  return (
    <AuthContext.Provider value={{ session, user, status, booting }}>
      {children}
    </AuthContext.Provider>
  );
}
