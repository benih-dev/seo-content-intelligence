import { ArrowRight } from "lucide-react";
import { date, label } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Badge, Panel } from "./ui";

export function ActivityPanel({ run }: { run: Run }) {
  return (
    <div className="panel-stack">
      <div className="two-column">
        <Panel title="Usage & cost" eyebrow="NO HIDDEN GENERATION">
          <div className="metric-grid">
            <div>
              <small>Recorded spend</small>
              <strong>${run.usage.cost_usd.toFixed(4)}</strong>
            </div>
            <div>
              <small>Tokens</small>
              <strong>{run.usage.tokens.toLocaleString()}</strong>
            </div>
            <div>
              <small>Model calls</small>
              <strong>{run.usage.calls.length}</strong>
            </div>
            <div>
              <small>Automatic revisions</small>
              <strong>{run.revision_count}</strong>
            </div>
          </div>
        </Panel>
        <Panel title="Worker jobs" eyebrow="DURABLE QUEUE">
          <div className="job-list">
            {run.jobs.map((j) => (
              <div key={j.id}>
                <span className="mono">{j.id.slice(0, 8)}</span>
                <span>
                  {j.attempts} attempt{j.attempts !== 1 && "s"}
                </span>
                <Badge value={j.status} />
                {j.error && <p className="error-text">{j.error}</p>}
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="Model usage detail">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Task</th>
                <th>Model</th>
                <th>Input / output tokens</th>
                <th>Latency</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {run.usage.calls.map((c, i) => (
                <tr key={i}>
                  <td>{label(c.task)}</td>
                  <td className="mono">{c.model}</td>
                  <td>
                    {c.prompt_tokens} / {c.completion_tokens}
                  </td>
                  <td>{c.latency_ms} ms</td>
                  <td>${c.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Approval decisions" eyebrow="HUMAN REVIEW RECORD">
        {run.approvals.length ? run.approvals.toReversed().map((approval) => (
          <article key={approval.id} className="timeline-item">
            <div>
              <div className="timeline-top">
                <strong>{label(approval.stage)} · {label(approval.decision)}</strong>
                <time>{date(approval.created_at)}</time>
              </div>
              <p>{approval.comment.trim() || "No reviewer comment provided."}</p>
              <small>{approval.actor_id}</small>
            </div>
          </article>
        )) : <p className="muted">No approval decisions recorded yet.</p>}
      </Panel>
      <Panel title="Audit trail" eyebrow="EVERY STAGE. EVERY DECISION.">
        <div className="timeline">
          {run.audit.toReversed().map((event) => (
            <article key={event.id} className="timeline-item">
              <span
                className={`timeline-dot ${event.actor === "user" ? "human" : ""}`}
              />
              <div>
                <div className="timeline-top">
                  <strong>
                    {event.action === "transition" ? (
                      <>
                        {label(String(event.data.from))}
                        <ArrowRight size={12} />
                        {label(String(event.data.to))}
                      </>
                    ) : (
                      label(event.action)
                    )}
                  </strong>
                  <time>{date(event.created_at)}</time>
                </div>
                <p>
                  {String(
                    event.data.reason ||
                      event.data.stage ||
                      event.data.task ||
                      event.data.error ||
                      "Recorded workflow event",
                  )}
                </p>
                <small>
                  {event.actor} ·{" "}
                  {event.data.artifact_ref
                    ? `artifact ${String(event.data.artifact_ref).slice(0, 8)} · `
                    : ""}
                  {event.id.slice(0, 8)}
                </small>
                <details>
                  <summary>Event payload</summary>
                  <pre>{JSON.stringify(event.data, null, 2)}</pre>
                </details>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
