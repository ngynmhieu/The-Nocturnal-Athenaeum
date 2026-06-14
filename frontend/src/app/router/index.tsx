import { createBrowserRouter } from "react-router";
import { AppLayout } from "../layouts";
import { ChatPage } from "@/modules/chat";
import { ProtectedRoute, LoginPage } from "@/modules/auth";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <ChatPage /> },
        ],
      },
    ],
  },
]);
