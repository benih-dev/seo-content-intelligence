"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Compass, KeyRound, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import type { Project, RunSummary } from "@/lib/types";
import {
  Empty,
  ErrorNotice,
  Panel,
  SectionTitle,
  Submit,
} from "@/components/ui";

export default function NewRunPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState("");
  const [mode, setMode] = useState("selected");
  const [keyword, setKeyword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [key] = useState(() => crypto.randomUUID());
  useEffect(() => {
    api<Project[]>("/projects")
      .then((p) => {
        setProjects(p);
        setProject(
          new URLSearchParams(window.location.search).get("project") ||
            p[0]?.id ||
            "",
        );
      })
      .catch((e) => setError(e.message));
  }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const run = await api<RunSummary>(
        "/runs",
        { project_id: project, mode, primary_keyword: keyword },
        "POST",
        { "Idempotency-Key": key },
      );
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <div className="page narrow">
      <Link href="/" className="back-link">
        ← Workspace
      </Link>
      <SectionTitle
        title="Start with a good question."
        description="Choose your keyword. We’ll help you find the angle, evidence, and words."
      />
      <ErrorNotice error={error} />
      {projects.length ? (
        <Panel title="New content run" eyebrow="FROM OPPORTUNITY TO ARTICLE">
          <form onSubmit={submit} className="form-stack">
            <label>
              Project
              <select
                value={project}
                onChange={(e) => setProject(e.target.value)}
                required
              >
                {projects.map((p) => (
                  <option value={p.id} key={p.id}>
                    {p.name} · {p.language.toUpperCase()} / {p.country}
                  </option>
                ))}
              </select>
            </label>
            <fieldset>
              <legend>How would you like to begin?</legend>
              <div className="mode-grid">
                {[
                  {
                    id: "selected",
                    title: "I have a keyword",
                    text: "Validate a specific search opportunity.",
                    Icon: KeyRound,
                  },
                  {
                    id: "discovery",
                    title: "Help me discover",
                    text: "Explore a shortlist from a seed topic.",
                    Icon: Compass,
                  },
                ].map(({ id, title, text, Icon }) => (
                  <label
                    key={id}
                    className={`mode-card ${mode === id ? "selected" : ""}`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value={id}
                      checked={mode === id}
                      onChange={() => setMode(id)}
                    />
                    <Icon size={21} />
                    <strong>{title}</strong>
                    <small>{text}</small>
                  </label>
                ))}
              </div>
            </fieldset>
            <label>
              {mode === "selected"
                ? "Primary keyword"
                : "Seed topic or keyword"}
              <input
                required
                minLength={2}
                maxLength={200}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="e.g. berkebun di balkon"
              />
              <small>
                One run creates one article. You approve the keyword before
                writing begins.
              </small>
            </label>
            <div className="notice">
              <ShieldCheck size={18} />
              <div>
                <strong>You’re in the editor’s seat.</strong>
                <p>
                  Keyword, brief, and final article each need your approval.
                  Nothing publishes automatically.
                </p>
              </div>
            </div>
            <div className="form-footer">
              <span>Research runs in the background.</span>
              <Submit busy={busy}>Start research</Submit>
            </div>
          </form>
        </Panel>
      ) : (
        !error && (
          <Empty title="Create a project first">
            <Link href="/projects/new">Set up your project</Link> to define the
            context for your first run.
          </Empty>
        )
      )}
    </div>
  );
}
