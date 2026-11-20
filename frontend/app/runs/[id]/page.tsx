"use client";
import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Clock3,
  Download,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, date, label } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Badge, ErrorNotice, Loading, Panel } from "@/components/ui";
import { KeywordPanel } from "@/components/keyword-panel";
import { BriefPanel } from "@/components/brief-panel";
import { ResearchPanel } from "@/components/research-panel";
import { ArticlePanel, Findings, SEOContent } from "@/components/article-panel";
import { ActivityPanel } from "@/components/activity-panel";

const tabs = [
  { id: "keywords", title: "Keyword research", number: "01" },
  { id: "brief", title: "Content brief", number: "02" },
  { id: "research", title: "Evidence & sources", number: "03" },
  { id: "article", title: "Article & review", number: "04" },
  { id: "seo", title: "SEO package", number: "05" },
  { id: "qa", title: "QA report", number: "06" },
  { id: "activity", title: "Activity", number: "07" },
];
const steps = [
  "Research",
  "Keyword review",
  "Strategy & brief",
  "Brief review",
  "Evidence & writing",
  "Final review",
  "Export",
];
function stageIndex(state: string) {
  return (
    (
      {
        draft: 0,
        ready_for_research: 0,
        researching: 0,
        keyword_review: 1,
        strategy: 2,
        brief_review: 3,
        evidence_research: 4,
        drafting: 4,
        optimizing: 4,
        qa: 4,
        revision_required: 4,
        final_review: 5,
        article_ready: 6,
        exported: 6,
      } as Record<string, number>
    )[state] ?? -1
  );
}

export default function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [run, setRun] = useState<Run>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("keywords");
  const initialized = useRef(false);
  const refresh = useCallback(async () => {
    const data = await api<Run>(`/runs/${id}`);
    setRun(data);
    return data;
  }, [id]);
  useEffect(() => {
    let live = true;
    api<Run>(`/runs/${id}`)
      .then((data) => {
        if (!live) return;
        setRun(data);
        if (!initialized.current) {
          const initial = new URLSearchParams(window.location.search).get(
            "tab",
          );
          setTab(
            tabs.some((t) => t.id === initial)
              ? initial!
              : data.drafts.length
                ? "article"
                : data.briefs.length
                  ? "brief"
                  : "keywords",
          );
          initialized.current = true;
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [id]);
  const working = !!run?.jobs.some((j) =>
    ["pending", "running"].includes(j.status),
  );
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => {
      refresh().catch((e) => setError(e.message));
    }, 2000);
    return () => clearInterval(timer);
  }, [working, refresh]);
  async function command(path: string, body?: unknown, method?: string) {
    setError("");
    setBusy(true);
    try {
      await api(`/runs/${id}/${path}`, body, method || "POST");
      await refresh();
      if (path === "approve" && (body as { stage: string }).stage === "keyword")
        setTab("brief");
      if (path === "approve" && (body as { stage: string }).stage === "brief")
        setTab("research");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const disabled = busy || working;
  const current = run ? stageIndex(run.state) : 0;
  return (
    <div className="page run-page">
      <div className="breadcrumbs">
        <Link href="/">
          <ArrowLeft size={13} />
          Projects
        </Link>
        <ChevronRight size={12} />
        {run && (
          <>
            <Link href={`/projects/${run.project_id}`}>
              {run.context.project?.name || "Project"}
            </Link>
            <ChevronRight size={12} />
            <span>Content run</span>
          </>
        )}
      </div>
      <ErrorNotice error={error} />
      {!run ? (
        !error && <Loading />
      ) : (
        <>
          <div className="run-heading">
            <div>
              <div className="eyebrow">
                CONTENT WORKBENCH{" "}
                <span className="run-short-id">/ {run.id.slice(0, 8)}</span>
              </div>
              <h1>{run.primary_keyword}</h1>
              <div className="run-subtitle">
                <span>{run.context.project?.name || "Project"}</span>
                <span>·</span>
                <span>{run.locale}</span>
                <span>·</span>
                <span>
                  {run.mode === "discovery"
                    ? "Discovery mode"
                    : "Selected keyword"}
                </span>
                <span>·</span>
                <span>Created {date(run.created_at)}</span>
              </div>
            </div>
            <div className="run-heading-actions">
              <Badge value={run.state} />
              {["failed", "paused", "needs_human_research"].includes(
                run.state,
              ) && (
                <button
                  className="button"
                  disabled={disabled}
                  onClick={() => command("retry")}
                >
                  <RotateCcw size={14} />
                  Retry run
                </button>
              )}
              {[
                "draft",
                "ready_for_research",
                "keyword_review",
                "brief_review",
                "failed",
                "blocked",
                "paused",
                "needs_human_research",
              ].includes(run.state) && (
                <button
                  className="button quiet"
                  disabled={disabled}
                  onClick={() => {
                    if (confirm("Cancel this content run?")) command("cancel");
                  }}
                >
                  <X size={14} />
                  Cancel
                </button>
              )}
            </div>
          </div>
          <div className="stepper" aria-label="Workflow progress">
            {steps.map((step, i) => (
              <div
                className={`step ${i < current || run.state === "exported" ? "done" : i === current ? "current" : ""}`}
                key={step}
              >
                <span>
                  {i < current || run.state === "exported" ? (
                    <Check size={12} />
                  ) : (
                    i + 1
                  )}
                </span>
                <strong>{step}</strong>
                {i < steps.length - 1 && <div className="step-line" />}
              </div>
            ))}
          </div>
          <div className="run-status-strip">
            <span>
              {working ? (
                <>
                  <LoaderCircle size={14} className="spin" />
                  Worker is processing · {label(run.state)}
                  <span className="poll-label">Live updates every 2s</span>
                </>
              ) : (
                <>
                  <Clock3 size={14} />
                  {run.state.endsWith("review")
                    ? "Waiting for your review"
                    : run.state === "exported"
                      ? "Article package approved and exported"
                      : label(run.state)}
                </>
              )}
            </span>
            <span>
              <ShieldCheck size={14} />
              Human approval at every key decision{" "}
              <span className="strip-divider">|</span>$
              {run.usage.cost_usd.toFixed(4)} ·{" "}
              {run.usage.tokens.toLocaleString()} tokens
            </span>
          </div>
          {run.error && (
            <div className="notice error">
              <strong>Run stopped:</strong> {run.error}
            </div>
          )}
          {run.state === "exported" && (
            <div className="export-success">
              <div>
                <Check size={18} />
                <strong>Your article package is ready.</strong>
                <span>Approved, versioned, and yours to publish.</span>
              </div>
              <div>
                {run.exports.map((fmt) => (
                  <a
                    key={fmt}
                    href={`/api/runs/${run.id}/export/${fmt}`}
                    className="button"
                    download
                  >
                    <Download size={14} />
                    {fmt.toUpperCase()}
                  </a>
                ))}
              </div>
            </div>
          )}
          <div
            className="tabs run-tabs"
            role="tablist"
            aria-label="Run sections"
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                onClick={() => setTab(t.id)}
              >
                <span className="tab-number">{t.number}</span>
                {t.title}
                {t.id === "research" && !!run.sources.length && (
                  <span className="count">{run.sources.length}</span>
                )}
              </button>
            ))}
          </div>
          <div
            id={`panel-${tab}`}
            role="tabpanel"
            aria-label={tabs.find((t) => t.id === tab)?.title}
          >
            {tab === "keywords" && (
              <KeywordPanel
                key={run.keywords.map((k) => k.id).join()}
                run={run}
                command={command}
                busy={disabled}
              />
            )}
            {tab === "brief" && (
              <BriefPanel
                key={run.briefs.at(-1)?.id || "waiting"}
                run={run}
                brief={run.briefs.at(-1)}
                command={command}
                busy={disabled}
              />
            )}
            {tab === "research" && <ResearchPanel run={run} />}
            <div hidden={tab !== "article"}>
              <ArticlePanel
                key={run.drafts.at(-1)?.id || run.id}
                run={run}
                command={command}
                busy={disabled}
              />
            </div>
            {tab === "seo" && <SEOContent run={run} />}
            {tab === "qa" && (
              <Panel
                title="Editorial quality review"
                eyebrow={`DRAFT VERSION ${run.drafts.at(-1)?.version || "—"}`}
              >
                <Findings
                  review={run.qa_reviews.findLast(
                    (review) => review.draft_id === run.drafts.at(-1)?.id,
                  )}
                />
                {["final_review", "blocked"].includes(run.state) && (
                  <button
                    className="button primary"
                    onClick={() => setTab("article")}
                  >
                    {run.state === "blocked"
                      ? "Open article to fix findings"
                      : "Review article & approve"}
                    <ArrowRight size={15} />
                  </button>
                )}
              </Panel>
            )}
            {tab === "activity" && <ActivityPanel run={run} />}
          </div>
        </>
      )}
    </div>
  );
}
