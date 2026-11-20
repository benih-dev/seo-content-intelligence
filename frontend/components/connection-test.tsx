"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export interface ConnectionResult {
  ok: boolean;
  message: string;
  hint: string;
}

export function ConnectionResultNotice({ result }: { result?: ConnectionResult }) {
  return <div aria-live="polite" role="status">
    {result && <div className={`notice ${result.ok ? "success" : "error"}`}><div><strong>{result.message}</strong><p>{result.hint}</p></div></div>}
  </div>;
}

export function ConnectionTest({ kind }: { kind: "llm" | "serp" | "keyword" }) {
  const [result, setResult] = useState<ConnectionResult>();
  const [busy, setBusy] = useState(false);
  async function test() {
    setBusy(true); setResult(undefined);
    try {
      setResult(await api<ConnectionResult>(`/settings/test/${kind}`, {}));
    } catch {
      setResult({ ok: false, message: "Connection test could not be completed.", hint: "Check your session and API availability, then retry." });
    } finally { setBusy(false); }
  }
  return <div className="form-stack">
    <small>Tests saved settings only. Save changes first. Live tests make a small, potentially billable provider call.</small>
    <button className="button" type="button" disabled={busy} onClick={test} aria-label={`Test ${kind.toUpperCase()} connection`}>
      {busy ? "Testing…" : `Test ${kind.toUpperCase()} connection`}
    </button>
    <ConnectionResultNotice result={result} />
  </div>;
}
