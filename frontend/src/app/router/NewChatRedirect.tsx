import { randomUUID } from "@/shared/lib";
import { useLayoutEffect, useState } from "react";
import { useNavigate } from "react-router";

/** Landing element for "/": mints a fresh conversation id and redirects to /c/:id
 *  before the browser paints, so a new chat opens directly on its own URL. Because every
 *  chat then lives under the single /c/:conversationId route, sending the first message
 *  never changes routes — no remount, no flash. The `isNew` state tells ChatPage to skip
 *  the history fetch for this not-yet-persisted id. */
export function NewChatRedirect() {
  const navigate = useNavigate();
  const [id] = useState(() => randomUUID());

  useLayoutEffect(() => {
    navigate(`/c/${id}`, { replace: true, state: { isNew: true } });
  }, [id, navigate]);

  return null;
}
