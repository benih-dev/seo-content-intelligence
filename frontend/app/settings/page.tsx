"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AppSettings, PublicSetting, SecretSetting, secretStatus, settingsPatch } from "@/lib/settings";
import { ErrorNotice, Loading, Panel, SectionTitle } from "@/components/ui";

export default function SettingsPage() {
  const [saved, setSaved] = useState<AppSettings>();
  const [values, setValues] = useState<Record<PublicSetting, string>>();
  const [secrets, setSecrets] = useState<Partial<Record<SecretSetting, string | null>>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api<AppSettings>("/settings").then(data => {
      if (live) { setSaved(data); setValues(data); }
    }).catch(() => { if (live) setError("Settings could not be loaded. Please reload to retry."); });
    return () => { live = false; };
  }, []);

  function publicInput(key: PublicSetting, label: string, hint: string) {
    return (
      <label className="field" key={key}>
        <span>{label}</span>
        <input name={key} value={values?.[key] || ""} aria-describedby={`${key}-hint`} disabled={busy}
          onChange={event => { setValues(current => current && { ...current, [key]: event.target.value }); setMessage(""); }} />
        <small id={`${key}-hint`}>{hint}</small>
      </label>
    );
  }

  function secretInput(key: SecretSetting, label: string) {
    if (!saved) return null;
    return (
      <div className="settings-secret" key={key}>
        <label className="field" htmlFor={key}>
          <span>{label}</span>
          <input id={key} name={key} type="password" autoComplete="new-password" value={secrets[key] || ""}
            aria-describedby={`${key}-status ${key}-hint`} disabled={busy}
            onChange={event => { setSecrets(current => ({ ...current, [key]: event.target.value })); setMessage(""); }} />
          <small id={`${key}-hint`}>Leave empty to keep the current key. Clear removes only the saved app value.</small>
        </label>
        <div className="settings-secret-status" id={`${key}-status`} aria-live="polite">
          <span className={`badge ${saved[key].configured ? "green" : "blue"}`}>{secretStatus(saved[key])}</span>
          {secrets[key] === null && <small>Saved value will be cleared on save; environment fallback may remain configured.</small>}
          {secrets[key] && <small>Replacement pending save</small>}
          <button type="button" className="button" aria-label={`Clear saved ${label}`} disabled={busy || saved[key].source !== "db"}
            onClick={() => { setSecrets(current => ({ ...current, [key]: null })); setMessage(""); }}>Clear</button>
        </div>
      </div>
    );
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!saved || !values) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await api<AppSettings>("/settings", settingsPatch(saved, values, secrets), "PUT");
      setSaved(data); setValues(data); setSecrets({}); setMessage("Settings saved. New provider calls use these settings without a restart.");
    } catch {
      setError("Settings could not be saved. Check the fields and HTTP(S) URLs, then retry.");
      setSecrets({});
    } finally { setBusy(false); }
  }

  return (
    <div className="page narrow">
      <SectionTitle title="Settings" description="Configure the providers used by this workspace." />
      <div className="notice warning">No login is enabled. Anyone who can reach this app can change provider settings. Keep access private.</div>
      <p className="muted">Keys are stored in the app database in plaintext and are write-only in this interface: saved keys are never returned. Protect database files and backups. A saved value overrides the environment; clearing it restores the environment fallback.</p>
      <ErrorNotice error={error} />
      {!saved || !values ? (!error && <Loading />) : (
        <form className="panel-stack" onSubmit={save} autoComplete="off">
          <div className="settings-modes" aria-label="Active provider modes">
            <span className="badge blue">LLM: {saved.modes.llm === "mock" ? "Mock (offline)" : "Live"}</span>
            <span className="badge blue">SERP: {saved.modes.serp === "mock" ? "Mock (offline)" : "Live (DataForSEO)"}</span>
          </div>
          <Panel title="LLM" eyebrow="ARTICLE GENERATION">
            <div className="form-stack">
              {publicInput("llm_model", "Model", "Leave empty for mock mode. For OpenAI-compatible endpoints use openai/<model>.")}
              {publicInput("llm_api_base", "API base URL", "Optional HTTP(S) endpoint, e.g. http://host:8080/v1. Empty uses the provider default.")}
              {secretInput("llm_api_key", "LLM API key")}
            </div>
          </Panel>
          <Panel title="DataForSEO" eyebrow="KEYWORDS & SERP">
            <div className="form-stack">
              <label className="field"><span>SERP provider</span><select name="serp_provider" value={values.serp_provider} disabled={busy}
                onChange={event => { setValues(current => current && { ...current, serp_provider: event.target.value }); setMessage(""); }}>
                <option value="mock">Mock (offline)</option><option value="dataforseo">DataForSEO (live)</option>
              </select></label>
              {publicInput("dataforseo_login", "DataForSEO login", "Account login for live keyword and SERP requests.")}
              {secretInput("dataforseo_password", "DataForSEO password")}
            </div>
          </Panel>
          <Panel title="GitHub publishing" eyebrow="PULL REQUEST CONNECTOR">
            <div className="form-stack">
              {publicInput("github_api_url", "GitHub API URL", "Default: https://api.github.com. Repository and branch settings remain per project.")}
              {secretInput("github_token", "GitHub token")}
            </div>
          </Panel>
          <div className="settings-save">
            <button type="submit" className="button primary" disabled={busy || !Object.keys(settingsPatch(saved, values, secrets)).length}>{busy ? "Saving…" : "Save settings"}</button>
            <p role="status">{message}</p>
          </div>
        </form>
      )}
    </div>
  );
}
