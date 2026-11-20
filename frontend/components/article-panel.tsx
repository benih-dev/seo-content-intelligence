"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Check,
  ChevronDown,
  Download,
  FileCode2,
  FileText,
  GitCompareArrows,
  PencilLine,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { api, date, label } from "@/lib/api";
import type { QAReview, Run } from "@/lib/types";
import { Badge, Empty, ErrorNotice, Panel } from "./ui";
import type { Command } from "./keyword-panel";

export function Findings({ review }: { review?: QAReview }) {
  if (!review) return <Empty title="Quality review is pending" />;
  return (
    <div className="qa-content">
      <div className="qa-overview">
        <span className="qa-shield">
          <ShieldCheck size={24} />
        </span>
        <div>
          <strong>
            {review.data.human_resolution
              ? "Human review recorded"
              : review.data.status === "pass"
                ? "Ready for your editorial review"
                : "Review findings before proceeding"}
          </strong>
          <p>{review.data.summary}</p>
        </div>
        <Badge value={review.data.status} />
      </div>
      <div className="qa-dimensions">
        {review.data.dimensions.map((d) => (
          <span key={d}>
            <Check size={13} />
            {d}
          </span>
        ))}
      </div>
      {review.data.findings.length ? (
        <div className="findings-list">
          {review.data.findings.map((f, i) => (
            <div className="finding" key={i}>
              <div className="finding-top">
                <strong>{f.finding}</strong>
                <Badge value={f.severity} />
              </div>
              <div className="finding-meta">
                {f.dimension} <span>·</span> {f.location}
              </div>
              <p>{f.action}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="qa-clear">
          <Check size={16} />
          No unresolved rule-based blockers or major findings.
        </div>
      )}
      {review.data.human_resolution && (
        <div className="notice success">
          Reviewer resolution: {review.data.human_resolution.comment}
        </div>
      )}
    </div>
  );
}

export function SEOContent({ run }: { run: Run }) {
  const meta = run.drafts.at(-1)?.metadata_json;
  if (!meta?.title)
    return <Empty title="SEO package comes after the first draft" />;
  return (
    <div className="panel-stack">
      <Panel title="Search appearance" eyebrow="SEO PACKAGE">
        <div className="search-preview">
          <small>
            {run.context.project?.domain || "Your website"} › {meta.slug}
          </small>
          <h3>{meta.title}</h3>
          <p>{meta.meta_description}</p>
        </div>
        <div className="seo-grid">
          {(
            [
              "title",
              "h1",
              "slug",
              "meta_description",
              "excerpt",
              "category",
              "primary_keyword",
              "locale",
            ] as const
          ).map((k) => (
            <div key={k}>
              <small>
                {label(k)}
                {k === "meta_description" &&
                  ` · ${meta[k]?.length || 0} characters`}
              </small>
              <p>{meta[k] || "Unavailable"}</p>
            </div>
          ))}
          <div>
            <small>Tags</small>
            <p>{meta.tags?.join(", ") || "Unavailable"}</p>
          </div>
        </div>
      </Panel>
      <Panel
        title="Visual direction"
        eyebrow="IMAGE BRIEF, NOT GENERATED ASSETS"
      >
        <dl className="definition-list">
          {Object.entries(meta.image_guidance || {}).map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}

export function ArticlePanel({
  run,
  command,
  busy,
}: {
  run: Run;
  command: Command;
  busy: boolean;
}) {
  const latest = run.drafts.at(-1);
  const [version, setVersion] = useState(latest?.version || 1);
  const [mode, setMode] = useState("preview");
  const [body, setBody] = useState(latest?.body_md || "");
  const [a, setA] = useState(run.drafts[0]?.version || 1);
  const [b, setB] = useState(latest?.version || 1);
  const [diff, setDiff] = useState("");
  const [error, setError] = useState("");
  const [diffBusy, setDiffBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [expert, setExpert] = useState(false);
  if (!latest)
    return (
      <Empty title="Your article is on its way">
        Writing begins after you approve the brief. Each draft is saved with a
        version history.
      </Empty>
    );
  const selected = run.drafts.find((d) => d.version === version) || latest;
  const review = run.qa_reviews.findLast((q) => q.draft_id === selected.id);
  const editable =
    ["final_review", "blocked"].includes(run.state) &&
    version === latest.version;
  async function compare() {
    setError("");
    setDiffBusy(true);
    try {
      const result = await api<{ diff: string }>(
        `/runs/${run.id}/drafts/diff?a=${a}&b=${b}`,
      );
      setDiff(result.diff || "No differences between these versions.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDiffBusy(false);
    }
  }
  return (
    <div className="panel-stack">
      {run.state === "final_review" && (
        <div className="gate-banner">
          <div className="gate-number">03</div>
          <div>
            <strong>One final read. Your name is on the decision.</strong>
            <p>
              Check the article, evidence, and QA before approving an export.
            </p>
          </div>
          <span className="gate-pill">FINAL REVIEW</span>
        </div>
      )}
      <div className="article-layout">
        <section className="article-panel">
          <div className="article-toolbar">
            <div className="segmented" aria-label="Article view">
              {[
                { id: "preview", text: "Preview", Icon: FileText },
                { id: "edit", text: "Markdown", Icon: PencilLine },
                { id: "diff", text: "Version diff", Icon: GitCompareArrows },
              ].map(({ id, text, Icon }) => (
                <button
                  key={id}
                  aria-pressed={mode === id}
                  onClick={() => setMode(id)}
                >
                  <Icon size={14} />
                  {text}
                </button>
              ))}
            </div>
            <label className="version-select">
              <span className="sr-only">Draft version</span>
              <select
                aria-label="Draft version"
                value={version}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setVersion(v);
                  setBody(
                    run.drafts.find((d) => d.version === v)?.body_md || "",
                  );
                }}
              >
                {run.drafts.map((d) => (
                  <option key={d.id} value={d.version}>
                    Version {d.version}
                    {d.version === latest.version ? " · Latest" : ""}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} />
            </label>
          </div>
          {mode === "preview" && (
            <article className="markdown article-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {selected.body_md}
              </ReactMarkdown>
            </article>
          )}
          {mode === "edit" && (
            <div className="editor-wrap">
              <label>
                Article Markdown
                <textarea
                  className="markdown-editor"
                  rows={30}
                  value={body}
                  readOnly={!editable}
                  onChange={(e) => setBody(e.target.value)}
                  spellCheck={false}
                />
              </label>
              <div className="editor-footer">
                <span>
                  {editable
                    ? "Saving creates a new version and reruns QA."
                    : "Read-only: select the latest draft at final review or blocked."}
                </span>
                <button
                  className="button primary"
                  disabled={
                    !editable || busy || body === latest.body_md || !body.trim()
                  }
                  onClick={() => command("draft", { body_md: body }, "PUT")}
                >
                  <Check size={15} />
                  Save new version
                </button>
              </div>
            </div>
          )}
          {mode === "diff" && (
            <div className="diff-wrap">
              <h2>What changed?</h2>
              <p className="muted">
                Compare immutable article versions, line by line.
              </p>
              <div className="diff-controls">
                <label>
                  From version
                  <select
                    value={a}
                    onChange={(e) => setA(Number(e.target.value))}
                  >
                    {run.drafts.map((d) => (
                      <option key={d.id} value={d.version}>
                        Version {d.version}
                      </option>
                    ))}
                  </select>
                </label>
                <span>→</span>
                <label>
                  To version
                  <select
                    value={b}
                    onChange={(e) => setB(Number(e.target.value))}
                  >
                    {run.drafts.map((d) => (
                      <option key={d.id} value={d.version}>
                        Version {d.version}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button"
                  disabled={diffBusy}
                  onClick={compare}
                >
                  {diffBusy ? "Comparing…" : "Compare"}
                </button>
              </div>
              <ErrorNotice error={error} />
              {diff && (
                <pre className="diff-output">
                  {diff.split("\n").map((line, i) => (
                    <span
                      className={
                        line.startsWith("+")
                          ? "diff-add"
                          : line.startsWith("-")
                            ? "diff-remove"
                            : ""
                      }
                      key={i}
                    >
                      {line}
                      {"\n"}
                    </span>
                  ))}
                </pre>
              )}
            </div>
          )}
          <div className="article-caption">
            <FileCode2 size={14} />
            Draft v{selected.version} · {date(selected.created_at)}
            <span>
              {selected.body_md.split(/\s+/).length.toLocaleString()} words
            </span>
          </div>
        </section>
        <aside className="article-aside" aria-label="Article details and exports">
          <Panel title="Article details">
            <dl className="definition-list">
              <div>
                <dt>Primary keyword</dt>
                <dd>{run.primary_keyword}</dd>
              </div>
              <div>
                <dt>Audience</dt>
                <dd>{run.context.project?.audience || "—"}</dd>
              </div>
              <div>
                <dt>Language / market</dt>
                <dd>{run.locale}</dd>
              </div>
              <div>
                <dt>Source library</dt>
                <dd>
                  {run.sources.length} sources · {run.evidence.length} claims
                </dd>
              </div>
              <div>
                <dt>Version note</dt>
                <dd>{selected.data.change_log}</dd>
              </div>
            </dl>
          </Panel>
          <Panel
            title="Quality assurance"
            aside={review && <Badge value={review.data.status} />}
          >
            <Findings review={review} />
          </Panel>
          <Panel title="Export package" eyebrow="PORTABLE BY DESIGN">
            <p className="muted">
              Article, metadata, sources, and evidence. No CMS lock-in.
            </p>
            <div className="export-buttons">
              {["md", "html", "json"].map((fmt) =>
                run.exports.includes(fmt) ? (
                  <a
                    className="button"
                    key={fmt}
                    href={`/api/runs/${run.id}/export/${fmt}`}
                    download
                  >
                    <Download size={15} />
                    {fmt === "md" ? "Markdown" : fmt.toUpperCase()}
                    <span>↓</span>
                  </a>
                ) : (
                  <button className="button" disabled key={fmt}>
                    <Download size={15} />
                    {fmt === "md" ? "Markdown" : fmt.toUpperCase()}
                    <span>Locked</span>
                  </button>
                ),
              )}
            </div>
            {!run.exports.length && (
              <small>Available after final approval and worker export.</small>
            )}
          </Panel>
        </aside>
      </div>
      {run.state === "final_review" && (
        <Panel
          title="The final editorial decision"
          eyebrow="HUMAN APPROVAL REQUIRED"
        >
          <div className="form-stack">
            {run.qa_reviews.at(-1)?.data.expert_review_required && (
              <div className="notice warning">
                <ShieldCheck size={20} />
                <div>
                  <strong>Expert review required</strong>
                  <p>
                    This topic may affect financial, health, legal, or safety
                    decisions. A qualified reviewer must check claims and source
                    suitability.
                  </p>
                  <label className="inline-label">
                    <input
                      type="checkbox"
                      checked={expert}
                      onChange={(e) => setExpert(e.target.checked)}
                    />
                    I confirm an appropriately qualified human has reviewed this
                    article and its sources.
                  </label>
                </div>
              </div>
            )}
            <label>
              Reviewer comment / revision instructions
              <textarea
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Record your editorial decision or describe the revision you need."
              />
            </label>
            {selected.id !== latest.id && (
              <div className="notice">
                <span>You are reviewing an older draft. Switch to the latest version before approving.</span>
                <button
                  className="button"
                  onClick={() => {
                    setVersion(latest.version);
                    setBody(latest.body_md);
                    setMode("preview");
                  }}
                >
                  Review latest version
                </button>
              </div>
            )}
            <div className="approval-actions">
              <p className="muted">
                Approval enables exports. Nothing is published automatically.
              </p>
              <button
                className="button"
                disabled={busy || !comment.trim()}
                onClick={() =>
                  command("approve", {
                    stage: "final",
                    decision: "request_revision",
                    comment,
                  })
                }
              >
                <RotateCcw size={15} />
                Request revision
              </button>
              <button
                className="button primary"
                disabled={
                  busy ||
                  selected.id !== latest.id ||
                  (!!run.qa_reviews.at(-1)?.data.expert_review_required &&
                    (!expert || !comment.trim()))
                }
                onClick={() =>
                  command("approve", {
                    stage: "final",
                    payload: { expert_reviewed: expert, draft_id: selected.id, draft_version: selected.version },
                    comment,
                  })
                }
              >
                <Check size={16} />
                Approve final article
              </button>
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
