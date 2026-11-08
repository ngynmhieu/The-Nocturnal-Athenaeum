const configuredSupabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;

/** In dev, a Supabase on this machine (the local Docker stack) is reached through
 *  the app's own origin — the Vite dev server proxies /auth/v1, /rest/v1,
 *  /storage/v1 and /realtime/v1 to it. That way a phone on the same Wi-Fi,
 *  which can't resolve "localhost" to this machine, still reaches it (and signed
 *  image URLs come back on an address the phone can load). A remote Supabase
 *  URL is used as-is. */
function resolveSupabaseUrl(url: string): string {
  // Only the dev server has that proxy; a production build (nginx) doesn't, so it
  // keeps the configured URL.
  if (!import.meta.env.DEV) return url;
  try {
    const host = new URL(url).hostname;
    if (host === "localhost" || host === "127.0.0.1") return window.location.origin;
  } catch {
    // fall through — let supabase-js report a malformed URL
  }
  return url;
}

export const env = {
  supabaseUrl: resolveSupabaseUrl(configuredSupabaseUrl),
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY as string,
};
