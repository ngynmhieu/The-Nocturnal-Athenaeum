import { Suspense } from "react";
import { createBrowserRouter } from "react-router";
import { AppLayout } from "../layouts";
import { ProtectedRoute, LoginPage } from "@/modules/auth";
import { LoadingDialog } from "@/shared/ui";
import { ChatPage } from "./lazyPages";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          {
            path: "/",
            element: (
              <Suspense fallback={<LoadingDialog />}>
                <ChatPage />
              </Suspense>
            ),
          },
        ],
      },
    ],
  },
]);
