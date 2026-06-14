# Module: `auth` (frontend)

> Per-module architecture doc. The frontend counterpart of `backend/docs/modules/auth.md`.
> Read `../frontend_guidelines.md` first for the rules (modular monolith + FSD) that govern every module.

## Responsibility

The frontend `auth` module answers one question for the rest of the app:
**"is someone signed in, and who are they?"**

We use **Supabase Auth** (Google OAuth). The flow:

1. The user clicks **Sign in with Google**.
2. `@supabase/supabase-js` runs the Google OAuth redirect and, on return, holds a
   **session** containing a signed **JWT** (access token) — stored and auto-refreshed
   by the SDK in `localStorage`.
3. Right after login, `AuthProvider` calls the backend **`POST /auth/me`** with that JWT
   to create/sync the `profiles` row and store the result as `AuthUser` in React state.
4. Every subsequent backend request carries `Authorization: Bearer <jwt>` via `fetchWithToken`.

The module **owns**:
- The login/logout UI and the OAuth trigger (`supabase.auth.signInWithOAuth`).
- Holding the current session in React state and exposing it via `useSession()`.
- Attaching the JWT to backend API calls (`shared/lib/http.ts`).
- Calling `POST /auth/me` once after login to sync the profile (inside `AuthProvider`).
- Guarding routes that require a signed-in user (`ProtectedRoute`).

The module does **not** own:
- JWT signing/validation → Supabase (issues) + backend (verifies).
- The `profiles` / `auth.users` tables → Supabase + backend.
- Any user menu UI → that lives in `app/layouts/` and consumes the module's public API.

---

## End-to-end flow

```
Sign-in
  user clicks "Sign in with Google"
    └─ supabase.auth.signInWithOAuth({ provider: "google" })
         └─ redirect to Google → back to the app
              └─ supabase-js stores the session (JWT) in localStorage
                   └─ onAuthStateChange fires → AuthProvider updates React state
                        └─ AuthProvider calls syncProfile(accessToken) → POST /auth/me
                             └─ backend upserts the profiles row, returns the profile
                                  └─ camelcase-keys converts snake_case → AuthUser

Authenticated request (e.g. chat)
  fetchWithToken("/chat", ...)
    └─ reads current session token from supabase-js
         └─ adds header: Authorization: Bearer <jwt>
              └─ backend Depends(get_current_user) validates it

Sign-out
  user clicks "Sign out"
    └─ supabase.auth.signOut()
         └─ onAuthStateChange fires with null → AuthProvider clears state
              └─ router redirects to /login
```

---

## Actual structure

```
frontend/src/
  shared/
    config/
      env.ts                 ← VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
      index.ts
    lib/
      supabase.ts            ← single @supabase/supabase-js client instance
      http.ts                ← fetchWithToken: adds Authorization: Bearer to any request
      index.ts
    api/
      chatApi.ts             ← chat endpoint caller (uses fetchWithToken)

  modules/
    auth/
      shared/
        authContext.ts       ← createContext + types (AuthContextValue, AuthStatus)
                               — context object only, no components/hooks (Fast Refresh rule)
        AuthProvider.tsx     ← component only: mounts session, calls syncProfile on login
        authApi.ts           ← syncProfile(): POST /auth/me, returns AuthUser via camelcase-keys
        useSession.ts        ← hook only: reads AuthContext, throws if outside AuthProvider
        index.ts
      entities/
        user/
          user.types.ts      ← AuthUser { id, email, fullName, avatarUrl }
          index.ts
        index.ts
      features/
        login/
          useLogin.ts        ← signInWithOAuth({ provider: "google" })
          index.ts
        logout/
          useLogout.ts       ← signOut()
          index.ts
        index.ts
      widgets/
        LoginButton.tsx      ← "Sign in with Google" button (used in LoginPage + SidebarFooter)
        index.ts
      pages/
        LoginPage.tsx        ← /login screen with owl mascot + LoginButton
        index.ts
      ProtectedRoute.tsx     ← redirects to /login if status !== "authenticated"
      index.ts               ← PUBLIC API (see below)

  app/
    layouts/
      Sidebar/
        components/
          UserMenu.tsx       ← sidebar footer user menu (trigger + portal dropdown)
                               uses useSession + useLogout from auth public API
          SidebarFooter.tsx  ← renders UserMenu when authenticated, LoginButton when anonymous
```

> **Why `UserMenu` is in `app/layouts/`, not `modules/auth/widgets/`:**
> The auth module is a service layer — it owns identity data and actions. UI that
> *presents* that data (trigger button, avatar, dropdown layout, portal positioning)
> is layout-specific and may differ between placements. The layout components consume
> `useSession()` and `useLogout()` from the auth public API; they do not live inside auth.

---

## The module's public API (`modules/auth/index.ts`)

```ts
export { AuthProvider, useSession } from "./shared";
export { LoginButton } from "./widgets";
export { ProtectedRoute } from "./ProtectedRoute";
export { LoginPage } from "./pages";
export { useLogin } from "./features";
export { useLogout } from "./features";
export type { AuthUser } from "./entities";
```

Everything else (`authContext.ts`, `authApi.ts`, `AuthProvider` internals) stays internal.
Layout components that need user identity import only from `@/modules/auth`.

---

## Key implementation notes

### Fast Refresh — 3-file context split

A single file cannot export both a component and a hook/context (Vite Fast Refresh rule).
The session context is split across three files:

| File | Exports | Rule |
|------|---------|------|
| `authContext.ts` | `AuthContext`, `AuthContextValue`, `AuthStatus` | context + types only, no JSX |
| `AuthProvider.tsx` | `AuthProvider` | component only |
| `useSession.ts` | `useSession` | hook only |

### Profile sync — `shared/authApi.ts`

`syncProfile(accessToken)` is a plain async function (no React), separated from
`AuthProvider` so it can be tested and reused without a component mount:

```ts
// called inside AuthProvider's onAuthStateChange, guarded by syncedRef
syncProfile(newSession.access_token)
  .then((profile) => { if (profile) setUser(profile); })
```

`syncedRef` tracks the last synced `user.id` so the call only fires once per login,
not on every token refresh.

### `camelcase-keys` instead of manual mappers

Backend responses use `snake_case` (`full_name`, `avatar_url`). Rather than maintaining
a manual mapper, `camelcase-keys` converts the raw JSON automatically:

```ts
return camelcaseKeys(raw, { deep: true }) as AuthUser;
```

`user.mappers.ts` was removed after this was adopted.

### `AuthUser` vs raw Supabase session

`AuthUser` comes from the backend `profiles` table (via `POST /auth/me`), not from the
raw Google session. This matters: `profiles` is the source of truth for display name and
avatar (the backend may enrich or normalise these fields). `useSession()` exposes `user: AuthUser | null`,
not the raw Supabase `User` object.

### JWT validation on mount

`AuthProvider` calls `supabase.auth.getClaims()` on mount to verify the persisted JWT
(signature + expiry) before trusting it. A failure sets status to `"anonymous"`.
`getSession()` is also called for the initial state read, and `onAuthStateChange`
handles all subsequent login/logout/refresh events.

---

## Wiring into the app shell

### `App.tsx`
```tsx
import { AuthProvider } from "@/modules/auth";

<AuthProvider>
  <RouterProvider router={router} />
</AuthProvider>
```

### `app/router/index.tsx`
```tsx
import { ProtectedRoute, LoginPage } from "@/modules/auth";

createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [{ path: "/", element: <ChatPage /> }],
      },
    ],
  },
]);
```

### `vite.config.ts` — `/auth` proxy
```ts
"/auth": {
  target: `http://${process.env.BACKEND_HOST ?? "localhost"}:${process.env.BACKEND_PORT ?? "8000"}`,
  changeOrigin: true,
},
```

### `SidebarFooter.tsx` — reads auth state
```tsx
import { useSession, LoginButton } from "@/modules/auth";
import { UserMenu } from "./UserMenu";

const { status } = useSession();
// renders <UserMenu /> when authenticated, <LoginButton /> when anonymous
```

---

## Dependency rules (flow downward only)

```
app/router, App.tsx, app/layouts
    └─→ modules/auth (public API only: AuthProvider, ProtectedRoute, LoginButton, useSession, useLogout)

modules/auth
    └─→ shared/lib    (supabase, fetchWithToken)
    └─→ shared/config (env)

shared/api/chatApi  ──> shared/lib/http (fetchWithToken)  ──> shared/lib/supabase  ──> shared/config/env
```

- `auth` depends only on `shared/` — never on another business module.
- Layout components (`app/layouts/`) may import from `modules/auth` public API — `app/` is allowed to depend on modules.
- Other modules never import auth internals — only through `@/modules/auth`.

---

## Deferred / future

- **Token-expiry UX**: supabase-js auto-refreshes; add a global 401 handler in `fetchWithToken`
  that signs the user out if a refresh ultimately fails.
- **Per-conversation ownership**: once chat persistence lands, scope conversations by `user.id`.
- **More providers** (GitHub, etc.): add the provider in the Supabase dashboard and a second
  button — no architectural change needed.
- **Migrate to publishable/secret keys** before the legacy `anon`/`service_role` keys are
  deprecated (end of 2026).
