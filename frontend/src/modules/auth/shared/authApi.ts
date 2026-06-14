import camelcaseKeys from "camelcase-keys";
import type { AuthUser } from "../entities";

export async function syncProfile(accessToken: string): Promise<AuthUser | null> {
  const res = await fetch("/auth/me", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) return null;
  const raw = await res.json();
  return camelcaseKeys(raw, { deep: true }) as AuthUser;
}
