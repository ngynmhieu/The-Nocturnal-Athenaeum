import { useState } from "react";
import { usePasswordLogin, type PasswordMode } from "../features/password-login";

const inputClass =
  "w-full rounded-lg border border-[var(--owl-brown)]/25 bg-[var(--owl-parchment)] px-3 py-2 text-sm text-[var(--owl-brown-deep)] placeholder:text-[var(--owl-brown-muted)]/70 focus:outline-none focus:border-[var(--owl-brown)]/60";

/** Email + password sign-in, with a switch to create the account once. */
export function PasswordLoginForm() {
  const [mode, setMode] = useState<PasswordMode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { submit, busy, error } = usePasswordLogin();

  return (
    <form
      className="flex w-full max-w-xs flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        void submit(mode, email.trim(), password);
      }}
    >
      <input
        type="email"
        required
        autoComplete="email"
        placeholder="Email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        className={inputClass}
      />
      <input
        type="password"
        required
        minLength={6}
        autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
        placeholder="Password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        className={inputClass}
      />
      {error && <p className="text-xs text-[var(--owl-brown-deep)]">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="rounded-lg border border-[var(--owl-brown)]/30 px-3 py-2 text-sm font-medium text-[var(--owl-brown-deep)] transition-colors hover:bg-[var(--owl-brown)]/10 cursor-pointer disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? "Please wait…" : mode === "sign-in" ? "Sign in with email" : "Create account"}
      </button>
      <button
        type="button"
        onClick={() => setMode(mode === "sign-in" ? "sign-up" : "sign-in")}
        className="text-xs text-[var(--owl-brown-muted)] underline-offset-2 hover:underline cursor-pointer"
      >
        {mode === "sign-in" ? "No account yet? Create one" : "Have an account? Sign in"}
      </button>
    </form>
  );
}
