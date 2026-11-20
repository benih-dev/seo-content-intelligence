"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  FileCheck2,
  FolderOpen,
  Globe2,
  Plus,
  Workflow,
} from "lucide-react";
import { api, date } from "@/lib/api";
import type { Project, RunSummary } from "@/lib/types";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  SectionTitle,
} from "@/components/ui";

export default function ProjectsPage() {
  const [data, setData] = useState<{
    projects: Project[];
    runs: RunSummary[];
  }>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Project[]>("/projects"), api<RunSummary[]>("/runs")])
      .then(([projects, runs]) => setData({ projects, runs }))
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="page">
      <SectionTitle
        title="Good content starts here."
        description="Your projects, research, and articles. One clear workflow."
      >
        <Link className="button primary" href="/projects/new">
          <Plus size={16} />
          New project
        </Link>
      </SectionTitle>
      <ErrorNotice error={error} />
      {!data ? (
        !error && <Loading />
      ) : (
        <>
          <div className="stats-grid">
            <div className="stat">
              <span>
                Active projects
                <FolderOpen size={17} />
              </span>
              <strong>{data.projects.length}</strong>
              <small>Distinct voices. Shared standards.</small>
            </div>
            <div className="stat">
              <span>
                Content runs
                <Workflow size={17} />
              </span>
              <strong>{data.runs.length}</strong>
              <small>From a question to a complete article.</small>
            </div>
            <div className="stat">
              <span>
                Ready to export
                <FileCheck2 size={17} />
              </span>
              <strong>
                {
                  data.runs.filter((r) =>
                    ["exported", "article_ready"].includes(r.state),
                  ).length
                }
              </strong>
              <small>Reviewed, approved, and portable.</small>
            </div>
          </div>
          <div className="section-heading">
            <h2>
              Your projects{" "}
              <span className="count">{data.projects.length}</span>
            </h2>
            <span>Organized around your audience</span>
          </div>
          {data.projects.length === 0 ? (
            <Empty title="Make room for your next great article">
              <Link href="/projects/new">Create your first project</Link> to
              define your audience and editorial voice.
            </Empty>
          ) : (
            <div className="project-grid">
              {data.projects.map((project, index) => (
                <Link
                  href={`/projects/${project.id}`}
                  className="project-card"
                  key={project.id}
                >
                  <div className="card-top">
                    <span className={`project-avatar color-${index % 3}`}>
                      {project.name[0]}
                    </span>
                    <ArrowRight size={18} />
                  </div>
                  <h3>{project.name}</h3>
                  <span className="domain">
                    <Globe2 size={13} />
                    {new URL(project.domain).hostname}
                  </span>
                  <p>{project.niche}</p>
                  <div className="project-card-footer">
                    <span>
                      {project.language.toUpperCase()} · {project.country}
                    </span>
                    <span>
                      {
                        data.runs.filter((r) => r.project_id === project.id)
                          .length
                      }{" "}
                      runs
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
          <div className="section-heading spaced">
            <h2>Recent content runs</h2>
            <Link href="/runs/new">
              Start a run <ArrowRight size={14} />
            </Link>
          </div>
          {data.runs.length === 0 ? (
            <Empty title="Your first run is a keyword away">
              Start with a selected keyword or discover a new opportunity.
            </Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Keyword / article</th>
                    <th>Project</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.slice(0, 12).map((run) => (
                    <tr key={run.id}>
                      <td>
                        <Link className="table-title" href={`/runs/${run.id}`}>
                          {run.primary_keyword}
                        </Link>
                        <small>
                          {run.mode === "discovery"
                            ? "Keyword discovery"
                            : "Selected keyword"}{" "}
                          · {run.locale}
                        </small>
                      </td>
                      <td>
                        {data.projects.find((p) => p.id === run.project_id)
                          ?.name || "Project"}
                      </td>
                      <td>
                        <Badge value={run.state} />
                      </td>
                      <td className="muted">{date(run.created_at)}</td>
                      <td>
                        <Link
                          href={`/runs/${run.id}`}
                          aria-label={`Open ${run.primary_keyword}`}
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
    </div>
  );
}
