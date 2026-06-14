import { createContext } from "react";
import type { Session } from "@supabase/supabase-js";
import type { AuthUser } from "../entities";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  session: Session | null;
  user: AuthUser | null;
  status: AuthStatus;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
