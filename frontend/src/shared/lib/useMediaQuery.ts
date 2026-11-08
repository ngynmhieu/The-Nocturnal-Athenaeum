import { useSyncExternalStore } from "react";

/** Live result of a CSS media query (re-renders when it starts/stops matching). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false
  );
}

/** Phone-sized viewport — below Tailwind's `md` breakpoint (48rem). */
export const MOBILE_QUERY = "(max-width: 47.99rem)";
export const useIsMobile = () => useMediaQuery(MOBILE_QUERY);
