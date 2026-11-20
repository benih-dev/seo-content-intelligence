"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, date } from "@/lib/api";
import { logsPath } from "@/lib/diagnostics";
import { ErrorNotice, Panel, SectionTitle } from "@/components/ui";

interface LogEvent {
  time: string;
  level: string;
  stage?: string;
  run_id?: string;
  provider: string;
  model?: string;
  status?: number;
  duration_ms?: number;
  message: string;
  error?: { hint: string; category: string };
}

export default function LogsPage() {
  const [rows, setRows] = useState<LogEvent[]>([]);
  const [runId, setRunId] = useState("");
  const [level, setLevel] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  async function load(run: string, severity: string) {
    setBusy(true); setError("");
    try { setRows(await api<LogEvent[]>(logsPath(run, severity))); }
    catch { setError("Logs could not be loaded. Check your session, then refresh."); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    const run = new URLSearchParams(window.location.search).get("run_id") || "";
    let live = true;
    api<LogEvent[]>(logsPath(run, "")).then(data => {
      if (live) { setRows(data); setRunId(run); }
    }).catch(() => { if (live) setError("Logs could not be loaded. Check your session, then refresh."); })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, []);
  return <div className="page">
    <SectionTitle title="Logs" description="Recent provider calls and pipeline events. The newest 500 events are retained across the API and worker." />
    <form className="form-grid" onSubmit={event => { event.preventDefault(); void load(runId, level); }}>
      <label>Run ID<input value={runId} maxLength={36} placeholder="All runs" onChange={event => setRunId(event.target.value)} /></label>
      <label>Level<select value={level} onChange={event => setLevel(event.target.value)}><option value="">All levels</option><option value="info">Info</option><option value="error">Error</option></select></label>
      <button className="button" disabled={busy}>{busy ? "Loading…" : "Filter / refresh logs"}</button>
    </form>
    <ErrorNotice error={error} />
    <div className="panel-stack" aria-live="polite" aria-busy={busy}>
      {!busy && !error && !rows.length && <p>No events match these filters.</p>}
      {rows.map((row, index) => <Panel key={`${row.time}-${index}`} title={row.message} eyebrow={`${date(row.time)} · ${row.level.toUpperCase()}`}>
        <div className="settings-modes">
          <span>Stage: {row.stage || "provider"}</span><span>Provider: {row.provider}</span>
          {row.model && <span>Model: {row.model}</span>}
          <span>Status: {row.status ?? "—"}</span><span>Duration: {row.duration_ms == null ? "—" : `${row.duration_ms} ms`}</span>
        </div>
        {row.error && <p>{row.error.category}: {row.error.hint}</p>}
        {row.run_id ? <Link href={`/runs/${encodeURIComponent(row.run_id)}`}>Run {row.run_id}</Link> : <small>No run (connection test)</small>}
      </Panel>)}
    </div>
  </div>;
}
