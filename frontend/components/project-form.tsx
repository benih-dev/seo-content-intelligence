"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Project, ProjectInput } from "@/lib/types";
import { ErrorNotice, Panel, Submit } from "./ui";

export function ProjectForm({ project }: { project?: Project }) {
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
  const [rules, setRules] = useState(JSON.stringify(form.rules, null, 2));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function field(key: keyof ProjectInput, value: string) {
    setForm({ ...form, [key]: value });
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const parsed = JSON.parse(rules);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
        throw new Error("Editorial rules must be a JSON object.");
      const result = await api<Project>(
        project ? `/projects/${project.id}` : "/projects",
        { ...form, rules: parsed },
        project ? "PUT" : "POST",
      );
      if (project) window.location.reload();
      else router.push(`/projects/${result.id}`);
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
              value={form.name}
              onChange={(e) => field("name", e.target.value)}
              placeholder="e.g. Kebun Balkon"
            />
          </label>
          <label>
            Website domain
            <input
              required
              type="url"
              value={form.domain}
              onChange={(e) => field("domain", e.target.value)}
              placeholder="https://example.com"
            />
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
        <fieldset className="form-grid">
          <legend>GitHub pull request settings</legend>
          {([
            ["github_repo", "Repository (owner/name)", ""],
            ["base_branch", "Base branch", "main"],
            ["content_dir", "Content directory", "src/content/blog"],
          ] as const).map(([key, title, fallback]) => (
            <label key={key}>
              {title}
              <input
                value={form.publishing?.[key] ?? fallback}
                onChange={(e) => setForm({ ...form, publishing: {
                  ...form.publishing, [key]: e.target.value,
                } })}
                placeholder={key === "github_repo" ? "benih-dev/benihkode" : fallback}
              />
            </label>
          ))}
          <label>
            File extension
            <select value={form.publishing?.file_extension ?? "md"}
              onChange={(e) => setForm({ ...form, publishing: {
                ...form.publishing, file_extension: e.target.value as "md" | "mdx",
              } })}>
              <option value="md">md</option>
              <option value="mdx">mdx</option>
            </select>
          </label>
          <small>Creates a PR for review only. Never merges or publishes automatically.</small>
        </fieldset>
        <label>
          Business objective
          <input
            value={form.business_objective}
            onChange={(e) => field("business_objective", e.target.value)}
          />
        </label>
        <label>
          Editorial rules <span className="muted">(JSON object)</span>
          <textarea
            className="code-input"
            rows={4}
            value={rules}
            onChange={(e) => setRules(e.target.value)}
            spellCheck={false}
          />
          <small>
            Author/reviewer rules, exclusions, preferred categories, and style
            requirements.
          </small>
        </label>
        <ErrorNotice error={error} />
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
