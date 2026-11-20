"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ErrorNotice, Panel } from "@/components/ui";

export function AuthForm({ setup = false }: { setup?: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api(setup ? "/auth/setup" : "/auth/login", {
        username: fields.get("username"), password: fields.get("password"),
      });
      router.replace(setup ? "/login" : "/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to sign in. Please retry.");
      setBusy(false);
    }
  }
  return <Panel title={setup ? "Create admin account" : "Log in"} eyebrow="SEO CONTENT INTELLIGENCE">
    <p className="muted">{setup ? "First-time setup is available only while the users file is empty. Create your own account before sharing access to this app." : "Sign in with an account from this server’s local users file."}</p>
    <ErrorNotice error={error} />
    <form className="form-stack" onSubmit={submit}>
      <label className="field"><span>Username</span><input name="username" autoComplete="username" required maxLength={64}
        pattern={"[A-Za-z0-9][A-Za-z0-9_.\\-]*"} aria-describedby="username-hint" disabled={busy} /></label>
      <small className="muted" id="username-hint">Use letters, numbers, dots, underscores or hyphens (up to 64 characters).</small>
      <label className="field"><span>Password</span><input type="password" name="password" required minLength={setup ? 8 : 1} maxLength={1024}
        autoComplete={setup ? "new-password" : "current-password"} aria-describedby="password-hint" disabled={busy} /></label>
      <small className="muted" id="password-hint">At least 8 characters. Passwords are stored only as salted hashes.</small>
      <button type="submit" className="button primary" disabled={busy}>{busy ? "Please wait…" : setup ? "Create admin account" : "Log in"}</button>
    </form>
  </Panel>;
}
