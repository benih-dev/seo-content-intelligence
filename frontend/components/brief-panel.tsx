"use client";
import { useState } from "react";
import { Check, GripVertical, Plus, Trash2 } from "lucide-react";
import type { Brief, Run } from "@/lib/types";
import { Badge, Empty, Panel } from "./ui";
import type { Command } from "./keyword-panel";

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
  const [form, setForm] = useState(brief?.data);
  const editable = run.state === "brief_review";
  if (!form || !brief)
    return (
      <Empty title="Your editorial plan comes next">
        Approve the keyword to generate a strategy and brief.
      </Empty>
    );
  function outline(index: number, key: string, value: string | number) {
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
  const warnings = (run.artifacts.find((a) => a.stage === "strategy")?.data
    .overlap_warnings || []) as { url: string; reason: string }[];
  return (
    <div className="panel-stack">
      {editable && (
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
          command("approve", { stage: "brief", payload: { edits: form } });
        }}
      >
        <Panel
          title="Editorial direction"
          eyebrow="CONTENT BRIEF"
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
                onChange={(e) => setForm({ ...form, angle: e.target.value })}
              />
            </label>
            <div className="form-grid">
              <label>
                Audience
                <input
                  required
                  readOnly={!editable}
                  value={form.audience}
                  onChange={(e) =>
                    setForm({ ...form, audience: e.target.value })
                  }
                />
              </label>
              <label>
                Final search intent
                <input
                  required
                  readOnly={!editable}
                  value={form.intent}
                  onChange={(e) => setForm({ ...form, intent: e.target.value })}
                />
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
              <div className="outline-row" key={index}>
                <GripVertical size={16} className="muted" />
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
                      className="purpose-input"
                      aria-label={`Section purpose ${index + 1}`}
                      readOnly={!editable}
                      value={row.purpose}
                      onChange={(e) =>
                        outline(index, "purpose", e.target.value)
                      }
                    />
                  </label>
                </div>
                {editable && (
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove heading ${index + 1}`}
                    onClick={() =>
                      setForm({
                        ...form,
                        outline: form.outline.filter((_, i) => i !== index),
                      })
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            ))}
          </div>
          {editable && (
            <button
              type="button"
              className="button quiet"
              onClick={() =>
                setForm({
                  ...form,
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
        <div className="two-column">
          {(
            [
              {
                key: "questions",
                title: "Questions to answer",
                eyebrow: "SEARCHER NEEDS",
              },
              {
                key: "exclusions",
                title: "Keep out of scope",
                eyebrow: "EDITORIAL BOUNDARIES",
              },
              {
                key: "internal_links",
                title: "Internal links",
                eyebrow: "KNOWN INVENTORY URLS ONLY",
              },
              {
                key: "source_plan",
                title: "Research queries",
                eyebrow: "SOURCE PLAN",
              },
            ] as const
          ).map(({ key, title, eyebrow }) => (
            <Panel key={key} title={title} eyebrow={eyebrow}>
              <label>
                <span className="sr-only">{title}</span>
                <textarea
                  aria-label={title}
                  rows={4}
                  readOnly={!editable}
                  value={form[key].join("\n")}
                  onChange={(e) =>
                    setForm({ ...form, [key]: e.target.value.split("\n") })
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
              <p>Your edits are saved as a new approved brief version.</p>
            </div>
            <button className="button primary" type="submit" disabled={busy}>
              <Check size={16} />
              Approve brief & begin writing
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
