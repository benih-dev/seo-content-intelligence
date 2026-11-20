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
import { TabList } from "@/components/tab-list";

type ImportResult = {
  items: ContentItem[];
  failures: { url: string; error: string }[];
};

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
  const [importError, setImportError] = useState("");
  const [result, setResult] = useState<ImportResult>();
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
    setImportError("");
    setBusy(true);
    setResult(undefined);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const urls = String(form.get("urls") ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [url, ...parts] = line.split("|");
          const title = parts.join("|").trim();
          return { url: url.trim(), ...(title ? { title } : {}) };
        });
      if (!sitemap && (urls.length === 0 || urls.length > 200)) {
        throw new Error("Enter 1–200 URLs, one per line.");
      }
      const response = await api<ImportResult>(
        `/projects/${id}/${sitemap ? "sitemap" : "content-items"}`,
        sitemap ? { url: form.get("url") } : { items: urls },
      );
      setItems((current) => {
        const byId = new Map(current.map((item) => [item.id, item]));
        for (const item of response.items) byId.set(item.id, item);
        return [...byId.values()];
      });
      setResult(response);
      if (!sitemap && response.items.length > 0 && !response.failures.length) formElement.reset();
    } catch (e) {
      setImportError((e as Error).message);
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
          <TabList
            id="project"
            label="Project sections"
            selected={tab}
            onSelect={setTab}
            tabs={["overview", "profile", "inventory"].map((t) => ({ id: t, content: <>
                {t[0].toUpperCase() + t.slice(1)}
                {t === "inventory" && (
                  <span className="count">{items.length}</span>
                )}
              </> }))}
          />
          {["overview", "profile", "inventory"].filter((t) => t !== tab).map((t) => (
            <div key={t} id={`project-panel-${t}`} role="tabpanel" aria-labelledby={`project-tab-${t}`} hidden />
          ))}
          <div id={`project-panel-${tab}`} role="tabpanel" aria-labelledby={`project-tab-${tab}`} tabIndex={0}>
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
              <ProjectForm key={project.id} project={project} onSaved={setProject} />
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
                      <small>Use full HTTP(S) URLs from your website. Optional format: URL | page title.</small>
                    </label>
                    <button disabled={busy} className="button">
                      <Plus size={15} />
                      Add content
                    </button>
                  </form>
                </Panel>
              </div>
              <ErrorNotice error={importError} />
              {result && (
                <div className={`notice ${result.items.length && !result.failures.length ? "success" : "warning"}`} role="status">
                  <div>
                    <strong>
                      {result.items.length === 0
                        ? "No URLs added."
                        : `${result.items.length} ${result.items.length === 1 ? "URL" : "URLs"} saved.`}
                      {result.failures.length > 0 && ` ${result.failures.length} skipped.`}
                    </strong>
                    {result.failures.map(({ url, error }, index) => (
                      <p key={`${url}-${index}`}>{url ? `${url}: ` : ""}{error}</p>
                    ))}
                    {!result.items.length && !result.failures.length && (
                      <p>Check that your sitemap contains page URLs from this website.</p>
                    )}
                  </div>
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
                              {i.title && <small>{i.url}</small>}
                              {i.metadata_json?.sitemap_lastmod && (
                                <small>Sitemap last modified: {i.metadata_json.sitemap_lastmod}</small>
                              )}
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
          </div>
        </>
      )}
    </div>
  );
}
