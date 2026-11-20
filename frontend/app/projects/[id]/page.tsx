"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Plus, Trash2, Upload } from "lucide-react";
import { api, date } from "@/lib/api";
import type { ContentItem, Project, RunSummary } from "@/lib/types";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  Panel,
  SectionTitle,
} from "@/components/ui";
import { ProjectForm } from "@/components/project-form";

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project>();
  const [items, setItems] = useState<ContentItem[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  useEffect(() => {
    Promise.all([
      api<Project>(`/projects/${id}`),
      api<ContentItem[]>(`/projects/${id}/content-items`),
      api<RunSummary[]>(`/runs?project_id=${id}`),
    ])
      .then(([p, i, r]) => {
        setProject(p);
        setItems(i);
        setRuns(r);
      })
      .catch((e) => setError(e.message));
  }, [id]);
  async function importItems(
    event: React.FormEvent<HTMLFormElement>,
    sitemap: boolean,
  ) {
    event.preventDefault();
    setError("");
    setBusy(true);
    setResult("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const response = await api<{
        items: ContentItem[];
        failures: { url: string; error: string }[];
      }>(
        `/projects/${id}/${sitemap ? "sitemap" : "content-items"}`,
        sitemap
          ? { url: form.get("url") }
          : {
              items: String(form.get("urls"))
                .split("\n")
                .filter(Boolean)
                .map((line) => {
                  const [url, title] = line.split("|");
                  return { url: url.trim(), title: title?.trim() || "" };
                }),
            },
      );
      setItems(await api<ContentItem[]>(`/projects/${id}/content-items`));
      setResult(
        `Imported ${response.items.length} ${response.items.length === 1 ? "URL" : "URLs"}.${response.failures.length ? " Skipped: " + response.failures.map((x) => `${x.url}: ${x.error}`).join("; ") : " No errors."}`,
      );
      if (!sitemap && response.items.length > 0 && !response.failures.length) formElement.reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (
      !confirm(
        "Delete this project and all its runs and articles? This cannot be undone.",
      )
    )
      return;
    setBusy(true);
    try {
      await api(`/projects/${id}`, undefined, "DELETE");
      router.push("/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <Link href="/" className="back-link">
        ← All projects
      </Link>
      <ErrorNotice error={error} />
      {!project ? (
        !error && <Loading />
      ) : (
        <>
          <SectionTitle
            title={project.name}
            description={`${project.domain} · ${project.language.toUpperCase()} / ${project.country} · Profile v${project.version}`}
          >
            <Link href={`/runs/new?project=${id}`} className="button primary">
              <Plus size={16} />
              New content run
            </Link>
          </SectionTitle>
          <div className="tabs" role="tablist" aria-label="Project sections">
            {["overview", "profile", "inventory"].map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
              >
                {t[0].toUpperCase() + t.slice(1)}
                {t === "inventory" && (
                  <span className="count">{items.length}</span>
                )}
              </button>
            ))}
          </div>
          {tab === "overview" && (
            <>
              <div className="context-card">
                <div>
                  <div className="eyebrow">EDITORIAL DIRECTION</div>
                  <h2>{project.niche}</h2>
                  <p>For {project.audience}</p>
                </div>
                <div>
                  <small>Brand voice</small>
                  <p>{project.voice_profile}</p>
                </div>
                <div>
                  <small>Business objective</small>
                  <p>{project.business_objective}</p>
                </div>
              </div>
              <div className="section-heading">
                <h2>
                  Content runs <span className="count">{runs.length}</span>
                </h2>
                <span>One keyword. One considered article.</span>
              </div>
              {!runs.length ? (
                <Empty title="Start your first content run">
                  <Link href={`/runs/new?project=${id}`}>Choose a keyword</Link>{" "}
                  and turn research into something useful.
                </Empty>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Keyword</th>
                        <th>Mode</th>
                        <th>State</th>
                        <th>Updated</th>
                        <th>Open</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((r) => (
                        <tr key={r.id}>
                          <td>
                            <Link
                              className="table-title"
                              href={`/runs/${r.id}`}
                            >
                              {r.primary_keyword}
                            </Link>
                          </td>
                          <td>{r.mode}</td>
                          <td>
                            <Badge value={r.state} />
                          </td>
                          <td>{date(r.updated_at)}</td>
                          <td>
                            <Link
                              href={`/runs/${r.id}`}
                              aria-label={`Open ${r.primary_keyword}`}
                            >
                              <ArrowRight size={16} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
          {tab === "profile" && (
            <>
              <ProjectForm project={project} />
              <div className="danger-zone">
                <div>
                  <strong>Delete project</strong>
                  <p>
                    Remove this project and its application data. Active jobs
                    must finish first.
                  </p>
                </div>
                <button
                  disabled={busy}
                  onClick={remove}
                  className="button danger"
                >
                  <Trash2 size={15} />
                  Delete project
                </button>
              </div>
            </>
          )}
          {tab === "inventory" && (
            <>
              <div className="two-column">
                <Panel title="Import a sitemap" eyebrow="KNOWN CONTENT">
                  <form
                    onSubmit={(e) => importItems(e, true)}
                    className="form-stack"
                  >
                    <label>
                      Sitemap URL
                      <input
                        name="url"
                        type="url"
                        required
                        placeholder={`${project.domain}/sitemap.xml`}
                      />
                    </label>
                    <p className="muted">
                      Sitemap indexes supported. Failed URLs do not abort the
                      import.
                    </p>
                    <button disabled={busy} className="button">
                      <Upload size={15} />
                      {busy ? "Importing…" : "Import sitemap"}
                    </button>
                  </form>
                </Panel>
                <Panel
                  title="Add URLs manually"
                  eyebrow="INTERNAL LINK INVENTORY"
                >
                  <form
                    onSubmit={(e) => importItems(e, false)}
                    className="form-stack"
                  >
                    <label>
                      URLs, one per line
                      <textarea
                        required
                        name="urls"
                        rows={3}
                        placeholder={`${project.domain}/guide | Optional page title`}
                      />
                      <small>Optional format: URL | page title</small>
                    </label>
                    <button disabled={busy} className="button">
                      <Plus size={15} />
                      Add content
                    </button>
                  </form>
                </Panel>
              </div>
              {result && (
                <div className="notice" role="status">
                  {result}
                </div>
              )}
              <Panel title={`Known content · ${items.length} ${items.length === 1 ? "URL" : "URLs"}`}>
                {!items.length ? (
                  <Empty title="No content imported yet">
                    Add your existing pages to detect overlap and suggest
                    verified internal links.
                  </Empty>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Page</th>
                          <th>Status</th>
                          <th>Last seen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((i) => (
                          <tr key={i.id}>
                            <td>
                              <a href={i.url} target="_blank" rel="noreferrer">
                                {i.title || i.url}
                              </a>
                              <small>{i.url}</small>
                            </td>
                            <td>
                              <Badge value={i.status} />
                            </td>
                            <td>{date(i.last_seen_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </>
          )}
        </>
      )}
    </div>
  );
}
