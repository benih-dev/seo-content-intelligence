"use client";
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Check, Plus, Trash2 } from "lucide-react";
import { api, label } from "@/lib/api";
import type {
  Brief,
  BriefData,
  BriefLink,
  ContentItem,
  Run,
} from "@/lib/types";
import { Badge, Empty, Panel } from "./ui";
import type { Command } from "./keyword-panel";

const INTENTS = [
  "informational",
  "commercial",
  "transactional",
  "navigational",
  "mixed",
];

const LISTS = [
  { key: "questions", title: "Questions to answer", eyebrow: "SEARCHER NEEDS" },
  { key: "subtopics", title: "Subtopics to cover", eyebrow: "COVERAGE" },
  { key: "entities", title: "Entities to mention", eyebrow: "TOPICAL DEPTH" },
  { key: "examples", title: "Examples to include", eyebrow: "ORIGINAL VALUE" },
  {
    key: "exclusions",
    title: "Keep out of scope",
    eyebrow: "EDITORIAL BOUNDARIES",
  },
  { key: "source_plan", title: "Research queries", eyebrow: "SOURCE PLAN" },
] as const;

type ListKey = (typeof LISTS)[number]["key"];

export function normalizeBrief(data: BriefData): BriefData {
  return {
    ...data,
    rationale: data.rationale || "",
    differentiation: data.differentiation || "",
    ...Object.fromEntries(LISTS.map(({ key }) => [key, data[key] || []])),
    internal_links: (data.internal_links || []).map((link) =>
      typeof link === "string"
        ? {
            url: link,
            title: "",
            anchor: link,
            reason: "",
            status: "search_suggestion",
          }
        : link,
    ),
  };
}

export function outlineIssues(outline: BriefData["outline"]) {
  const issues: string[] = [];
  let previous = 0;
  outline.forEach((row, index) => {
    const name = row.heading.trim()
      ? `“${row.heading.trim()}”`
      : `Section ${index + 1}`;
    if (!row.heading.trim()) issues.push(`${name} needs a heading.`);
    if (!row.purpose.trim()) issues.push(`${name} needs a section purpose.`);
    if (previous === 0 && row.level !== 1)
      issues.push("The outline must start with the H1.");
    else if (row.level > previous + 1)
      issues.push(
        `${name} skips a heading level; use H${previous + 1} or lower.`,
      );
    previous = row.level;
  });
  if (outline.filter((row) => row.level === 1).length !== 1)
    issues.push("The outline needs exactly one H1.");
  if (outline.length < 2) issues.push("Add at least one section under the H1.");
  return [...new Set(issues)];
}

export function BriefPanel({
  run,
  brief,
  command,
  busy,
}: {
  run: Run;
  brief?: Brief;
  command: Command;
  busy: boolean;
}) {
  const [form, setForm] = useState(brief && normalizeBrief(brief.data));
  const [inventory, setInventory] = useState<ContentItem[]>([]);
  const [suggestion, setSuggestion] = useState("");
  const [issues, setIssues] = useState<string[]>([]);
  const editable = run.state === "brief_review";
  useEffect(() => {
    if (!editable) return;
    api<ContentItem[]>(`/projects/${run.project_id}/content-items`)
      .then(setInventory)
      .catch(() => setInventory([]));
  }, [editable, run.project_id]);
  if (!form || !brief)
    return (
      <Empty title="Your editorial plan comes next">
        Approve the keyword to generate a strategy and brief.
      </Empty>
    );
  function update(next: Partial<BriefData>) {
    setIssues([]);
    setForm((current) => current && { ...current, ...next });
  }
  function outline(index: number, key: string, value: string | number) {
    setIssues([]);
    setForm(
      (current) =>
        current && {
          ...current,
          outline: current.outline.map((row, i) =>
            i === index ? { ...row, [key]: value } : row,
          ),
        },
    );
  }
  function move(index: number, by: number) {
    if (!form) return;
    const rows = [...form.outline];
    [rows[index], rows[index + by]] = [rows[index + by], rows[index]];
    update({ outline: rows });
  }
  function links(next: BriefLink[]) {
    update({ internal_links: next });
  }
  const linked = new Set(form.internal_links.map((x) => x.url));
  const available = inventory.filter((x) => !linked.has(x.url));
  const warnings = (run.artifacts.find((a) => a.stage === "strategy")?.data
    .overlap_warnings || []) as { url: string; reason: string }[];
  return (
    <div className="panel-stack">
      {editable ? (
        <div className="gate-banner">
          <div className="gate-number">02</div>
          <div>
            <strong>A clear brief makes a better article.</strong>
            <p>
              Shape the angle and outline. Research and writing start only after
              your approval.
            </p>
          </div>
          <span className="gate-pill">YOUR REVIEW</span>
        </div>
      ) : (
        brief.status === "approved" && (
          <div className="notice success">
            <Check size={17} />
            <div>
              <strong>Brief version {brief.version} approved</strong>
              <p>
                This version is locked. Research and writing follow this plan.
              </p>
            </div>
          </div>
        )
      )}
      {warnings.map((w) => (
        <div className="notice warning" key={w.url}>
          <div>
            <strong>Existing content overlap</strong>
            <p>{w.reason}</p>
            <a href={w.url} target="_blank" rel="noreferrer">
              {w.url}
            </a>
          </div>
        </div>
      ))}
      <form
        className="panel-stack"
        onSubmit={(e) => {
          e.preventDefault();
          const found = outlineIssues(form.outline);
          setIssues(found);
          if (!found.length)
            command("approve", { stage: "brief", payload: { edits: form } });
        }}
      >
        <Panel
          title="Editorial direction"
          eyebrow="CONTENT STRATEGY"
          aside={
            <Badge value={brief.status}>
              Version {brief.version} · {brief.status}
            </Badge>
          }
        >
          <div className="form-stack">
            <label>
              Article angle
              <textarea
                rows={2}
                required
                readOnly={!editable}
                value={form.angle}
                onChange={(e) => update({ angle: e.target.value })}
              />
            </label>
            <div className="form-grid">
              <label>
                Why this angle fits
                <textarea
                  rows={3}
                  readOnly={!editable}
                  value={form.rationale}
                  onChange={(e) => update({ rationale: e.target.value })}
                />
              </label>
              <label>
                How it stands out
                <textarea
                  rows={3}
                  readOnly={!editable}
                  value={form.differentiation}
                  onChange={(e) => update({ differentiation: e.target.value })}
                />
              </label>
            </div>
            <div className="form-grid">
              <label>
                Audience
                <input
                  required
                  readOnly={!editable}
                  value={form.audience}
                  onChange={(e) => update({ audience: e.target.value })}
                />
              </label>
              <label>
                Final search intent
                <select
                  required
                  disabled={!editable}
                  value={form.intent}
                  onChange={(e) => update({ intent: e.target.value })}
                >
                  {[...new Set([form.intent, ...INTENTS])].map((x) => (
                    <option key={x} value={x}>
                      {label(x)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        </Panel>
        <Panel
          title="Build the article’s structure"
          eyebrow="OUTLINE"
          aside={
            <span className="muted">One H1 · logical H2 / H3 sections</span>
          }
        >
          <div className="outline-editor">
            {form.outline.map((row, index) => (
              <div
                className={`outline-row level-${row.level}`}
                key={index}
                data-testid="outline-row"
              >
                <label className="level-label">
                  <span className="sr-only">Heading level {index + 1}</span>
                  <select
                    aria-label={`Heading level ${index + 1}`}
                    disabled={!editable}
                    value={row.level}
                    onChange={(e) =>
                      outline(index, "level", Number(e.target.value))
                    }
                  >
                    {[1, 2, 3].map((level) => (
                      <option key={level} value={level}>
                        H{level}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="outline-fields">
                  <label>
                    <span className="sr-only">Heading {index + 1}</span>
                    <input
                      required
                      aria-label={`Heading ${index + 1}`}
                      placeholder="Section heading"
                      readOnly={!editable}
                      value={row.heading}
                      onChange={(e) =>
                        outline(index, "heading", e.target.value)
                      }
                    />
                  </label>
                  <label>
                    <span className="sr-only">Section purpose {index + 1}</span>
                    <input
                      required
                      className="purpose-input"
                      aria-label={`Section purpose ${index + 1}`}
                      placeholder="What should this section do for the reader?"
                      readOnly={!editable}
                      value={row.purpose}
                      onChange={(e) =>
                        outline(index, "purpose", e.target.value)
                      }
                    />
                  </label>
                </div>
                {editable && (
                  <div className="row-actions">
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Move heading ${index + 1} up`}
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Move heading ${index + 1} down`}
                      disabled={index === form.outline.length - 1}
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown size={15} />
                    </button>
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={`Remove heading ${index + 1}`}
                      onClick={() =>
                        update({
                          outline: form.outline.filter((_, i) => i !== index),
                        })
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {editable && (
            <button
              type="button"
              className="button quiet"
              onClick={() =>
                update({
                  outline: [
                    ...form.outline,
                    { level: 2, heading: "", purpose: "" },
                  ],
                })
              }
            >
              <Plus size={15} />
              Add section
            </button>
          )}
        </Panel>
        <Panel
          title="Internal links"
          eyebrow="FROM YOUR BLOG INVENTORY"
          aside={
            <span className="muted">
              {
                form.internal_links.filter((x) => x.status === "inventory")
                  .length
              }{" "}
              from inventory
            </span>
          }
        >
          <div className="link-list">
            {!form.internal_links.length && (
              <p className="muted">
                No related articles found in your inventory yet.
              </p>
            )}
            {form.internal_links.map((link, index) => (
              <div className="link-row" key={`${link.url}-${index}`}>
                <div className="link-main">
                  <div className="link-head">
                    <Badge
                      value={
                        link.status === "inventory" ? "approved" : "review"
                      }
                    >
                      {link.status === "inventory"
                        ? "From inventory"
                        : "Search suggestion"}
                    </Badge>
                    {link.url && (
                      <a href={link.url} target="_blank" rel="noreferrer">
                        {link.url}
                      </a>
                    )}
                  </div>
                  <input
                    aria-label={`Anchor text ${index + 1}`}
                    placeholder="Anchor text"
                    readOnly={!editable}
                    value={link.anchor}
                    onChange={(e) =>
                      links(
                        form.internal_links.map((x, i) =>
                          i === index ? { ...x, anchor: e.target.value } : x,
                        ),
                      )
                    }
                  />
                  {link.reason && <small>{link.reason}</small>}
                </div>
                {editable && (
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove link ${index + 1}`}
                    onClick={() =>
                      links(form.internal_links.filter((_, i) => i !== index))
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            ))}
          </div>
          {editable && (
            <div className="form-grid link-add">
              <label>
                Add a link from your inventory
                <select
                  value=""
                  disabled={!available.length}
                  onChange={(e) => {
                    const item = inventory.find(
                      (x) => x.url === e.target.value,
                    );
                    if (item)
                      links([
                        ...form.internal_links,
                        {
                          url: item.url,
                          title: item.title,
                          anchor: item.title || item.slug,
                          reason: "Selected from your inventory",
                          status: "inventory",
                        },
                      ]);
                  }}
                >
                  <option value="">
                    {available.length
                      ? "Choose an article…"
                      : "All inventory articles are linked"}
                  </option>
                  {available.map((x) => (
                    <option key={x.url} value={x.url}>
                      {x.title || x.url}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Topic to link once it exists
                <div className="inline-add">
                  <input
                    placeholder="e.g. Cara memilih pot"
                    value={suggestion}
                    onChange={(e) => setSuggestion(e.target.value)}
                  />
                  <button
                    type="button"
                    className="button quiet"
                    disabled={!suggestion.trim()}
                    onClick={() => {
                      links([
                        ...form.internal_links,
                        {
                          url: "",
                          title: suggestion.trim(),
                          anchor: suggestion.trim(),
                          reason: "",
                          status: "search_suggestion",
                        },
                      ]);
                      setSuggestion("");
                    }}
                  >
                    <Plus size={15} />
                    Add
                  </button>
                </div>
              </label>
            </div>
          )}
        </Panel>
        <div className="two-column">
          {LISTS.map(({ key, title, eyebrow }) => (
            <Panel key={key} title={title} eyebrow={eyebrow}>
              <label>
                <span className="sr-only">{title}</span>
                <textarea
                  aria-label={title}
                  rows={4}
                  readOnly={!editable}
                  value={form[key as ListKey].join("\n")}
                  onChange={(e) =>
                    update({ [key]: e.target.value.split("\n") })
                  }
                />
                <small>One item per line.</small>
              </label>
            </Panel>
          ))}
        </div>
        {editable && (
          <div className="approval-bar">
            <div>
              <strong>Approve the plan, then let research begin.</strong>
              <p>
                Edits are saved as a new brief version, and the approved version
                stays locked.
              </p>
              {issues.length > 0 && (
                <ul className="form-issues" role="alert">
                  {issues.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              )}
            </div>
            <button className="button primary" type="submit" disabled={busy}>
              <Check size={16} />
              Approve brief & begin research
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
