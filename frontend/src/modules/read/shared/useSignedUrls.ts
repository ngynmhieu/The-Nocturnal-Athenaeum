import { useEffect, useState } from "react";
import { createSignedUrls } from "@/shared/lib";

/** Batch-sign a set of Storage paths (private bucket → temporary CDN links) and
 *  return a path → signed-URL map. The reader signs a whole section at once,
 *  grids sign all covers at once.
 *
 *  Already-signed paths keep their URL when the set changes: only paths not yet
 *  in the map are signed. A fresh token is a different URL, so re-signing a
 *  whole section after removing or inserting one page would make every image
 *  re-download. */
export function useSignedUrls(paths: (string | null | undefined)[]): Record<string, string> {
  // Paths are `{user_id}/{...}/{uuid}.{ext}` — never contain "|", so a joined
  // string is a safe, stable dependency key (avoids re-signing on array identity).
  const key = paths.filter(Boolean).join("|");
  const [urls, setUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!key) return; // nothing to sign; the empty map is returned below
    const wanted = key.split("|");
    const missing = wanted.filter((path) => !(path in urls));
    if (missing.length === 0) return;
    let cancelled = false;
    createSignedUrls(missing)
      .then((signed) => {
        if (cancelled) return;
        setUrls((prev) => {
          const next = { ...prev };
          missing.forEach((path, i) => {
            if (signed[i]) next[path] = signed[i];
          });
          return next;
        });
      })
      .catch(() => {
        // leave the existing map; missing paths just show placeholders
      });
    return () => {
      cancelled = true;
    };
    // `urls` is read only to skip already-signed paths; re-running on every map
    // update would be redundant (the merge above never adds a missing path twice).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // While new paths are signing, their lookups simply miss — consumers show
  // placeholders until they land.
  return key ? urls : {};
}
