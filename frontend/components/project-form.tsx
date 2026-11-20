"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Project, ProjectInput } from "@/lib/types";
import { ErrorNotice, Panel, Submit } from "./ui";

function existingStructuredRules(rules: ProjectInput["rules"]) {
  return Object.fromEntries(
    Object.entries(rules).filter(([key, value]) => key !== "instructions" || typeof value !== "string"),
  );
}

export function ProjectForm({
  project,
  onSaved,
}: {
  project?: Project;
  onSaved?: (project: Project) => void;
}) {
  const router = useRouter();
  const [form, setForm] = useState<ProjectInput>(
    project || {
      name: "",
      domain: "",
      niche: "",
      audience: "",
      language: "id",
      country: "ID",
      voice_profile: "Clear, practical, helpful",
      rules: {},
      business_objective: "Educate readers",
    },
  );
  const [rules, setRules] = useState(
    typeof form.rules.instructions === "string" ? form.rules.instructions : "",
  );
  const [structuredRules, setStructuredRules] = useState(
    () => JSON.stringify(existingStructuredRules(form.rules), null, 2),
  );
  const hasStructuredRules = Object.keys(existingStructuredRules(form.rules)).length > 0;
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
function field(key: Exclude<keyof ProjectInput, "rules">, value: string) {
    setForm({ ...form, [key]: value });
    setSaved(false);
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      if (![form.name, form.domain, form.niche, form.audience].every((text) => text.trim())) {
        throw new Error("Enter a project name, website domain, niche, and audience.");
      }
      const domain = form.domain.trim();
      const websiteUrl = domain.includes("://") ? domain : `https://${domain}`;
      const website = URL.canParse(websiteUrl) ? new URL(websiteUrl) : null;
      if (!website || !["https:", "http:"].includes(website.protocol) || website.username || website.password || /\s/.test(domain)) {
        throw new Error("Enter a website domain such as example.com or https://example.com.");
      }
      let nextRules: ProjectInput["rules"] = {};
      if (hasStructuredRules) {
        try {
          const parsed = JSON.parse(structuredRules);
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
          nextRules = parsed;
        } catch {
          throw new Error('Existing structured rules must be a JSON object. Use {} to remove them.');
        }
      }
      if (rules.trim()) nextRules.instructions = rules.trim();
      const result = await api<Project>(
        project ? `/projects/${project.id}` : "/projects",
        { ...form, domain: website.origin, rules: nextRules },
        project ? "PUT" : "POST",
      );
      if (project) {
        setForm(result);
        setRules(rules.trim());
        setSaved(true);
        onSaved?.(result);
      } else router.push(`/projects/${result.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel
      title={project ? "Project profile" : "A home for your content"}
      eyebrow="CONTEXT & EDITORIAL DIRECTION"
    >
      <form onSubmit={submit} className="form-stack">
        <div className="form-grid">
          <label>
            Project name
            <input
              required
              maxLength={200}
              value={form.name}
              onChange={(e) => field("name", e.target.value)}
              placeholder="e.g. Kebun Balkon"
            />
          </label>
          <label>
            Website domain
            <input
              required
              value={form.domain}
              onChange={(e) => field("domain", e.target.value)}
              placeholder="example.com"
            />
            <small>Enter your domain or full website URL.</small>
          </label>
          <label>
            Niche / topic focus
            <input
              required
              value={form.niche}
              onChange={(e) => field("niche", e.target.value)}
              placeholder="What do you write about?"
            />
          </label>
          <label>
            Audience
            <input
              required
              value={form.audience}
              onChange={(e) => field("audience", e.target.value)}
              placeholder="Who are you helping?"
            />
          </label>
          <label>
            Article language
            <select
              value={form.language}
              onChange={(e) => field("language", e.target.value)}
            >
              <option value="id">Bahasa Indonesia</option>
              <option value="en">English</option>
            </select>
          </label>
          <label>
            Target country
            <input
              required
              minLength={2}
              maxLength={3}
              pattern="[A-Za-z]{2,3}"
              value={form.country}
              onChange={(e) => field("country", e.target.value.toUpperCase())}
              placeholder="ID"
            />
            <small>ISO country code, e.g. ID or US.</small>
          </label>
        </div>
        <label>
          Brand voice
          <textarea
            rows={2}
            value={form.voice_profile}
            onChange={(e) => field("voice_profile", e.target.value)}
          />
        </label>
        <label>
          Business objective
          <input
            value={form.business_objective}
            onChange={(e) => field("business_objective", e.target.value)}
          />
        </label>
        <label>
          Editorial rules
          <textarea
            rows={4}
            value={rules}
            placeholder="Use plain language. Cite original sources. Avoid promotional claims."
            onChange={(e) => {
              setRules(e.target.value);
              setSaved(false);
            }}
          />
          <small>
            Author/reviewer rules, exclusions, preferred categories, and style
            requirements.
          </small>
        </label>
        {hasStructuredRules && (
          <details>
            <summary>Existing structured rules</summary>
            <label>
              Structured rules (JSON)
              <textarea
                rows={4}
                className="code-input"
                value={structuredRules}
                onChange={(e) => {
                  setStructuredRules(e.target.value);
                  setSaved(false);
                }}
              />
            </label>
          </details>
        )}
        <ErrorNotice error={error} />
        {saved && <div className="notice success" role="status">Profile saved.</div>}
        <div className="form-footer">
          <span>Every run keeps a snapshot of this profile.</span>
          <Submit busy={busy}>
            {project ? "Save profile" : "Create project"}
          </Submit>
        </div>
      </form>
    </Panel>
  );
}
