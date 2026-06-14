import { RouterProvider } from "react-router";
import { router } from "./app/router";
import { AuthProvider } from "@/modules/auth";

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
