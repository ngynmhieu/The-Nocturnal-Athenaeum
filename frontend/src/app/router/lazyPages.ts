import { lazy } from "react";

// Code-split route components. Kept in their own file so the router config
// (which exports a non-component `router`) stays Fast Refresh-compliant.
export const ChatPage = lazy(() =>
  import("@/modules/chat").then((m) => ({ default: m.ChatPage }))
);
