import { createBrowserRouter } from "react-router";
import { AppLayout } from "../layouts";
import { ChatPage } from "@/modules/chat";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <ChatPage /> },
    ],
  },
]);
