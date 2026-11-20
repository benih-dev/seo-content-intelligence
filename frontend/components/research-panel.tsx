import { ArrowUpRight, BookOpen } from "lucide-react";
import { date, percent } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Badge, Empty, Panel } from "./ui";

export function ResearchPanel({ run }: { run: Run }) {
  if (!run.sources.length)
    return (
      <Empty title="Evidence before eloquence">
        Approve your brief to start collecting sources and building the evidence
        ledger.
      </Empty>
    );
  return (
    <div className="panel-stack">
      <div className="notice subtle">
        <BookOpen size={18} />
        <div>
          <strong>Sources are evidence, never instructions.</strong>
          <p>
            External content is treated as untrusted input. Demo summaries are
            not live-fetched verification; review the original context before
            publishing.
          </p>
        </div>
      </div>
      <Panel
        title="Evidence ledger"
        eyebrow={`${run.evidence.length} TRACEABLE CLAIMS`}
      >
        <div className="evidence-list">
          {run.evidence.map((item, index) => (
            <article key={item.id} className="evidence-item">
              <div className="evidence-number">
                E{String(index + 1).padStart(2, "0")}
              </div>
              <div>
                <div className="finding-top">
                  <h3>{item.claim}</h3>
                  <Badge value={item.review_status} />
                </div>
                <p>
                  {item.supporting_note.replaceAll(
                    /<\/?untrusted_source>/g,
                    "",
                  )}
                </p>
                <div className="evidence-meta">
                  <span>{percent(item.confidence)} confidence</span>
                  <span>{item.data.scope}</span>
                  <a href={item.data.url} target="_blank" rel="noreferrer">
                    Original source <ArrowUpRight size={13} />
                  </a>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Panel>
      <Panel title="Research library" eyebrow={`${run.sources.length} SOURCES`}>
        <div className="source-grid">
          {run.sources.map((source) => (
            <article key={source.id} className="source-card">
              <div className="source-publisher">
                <BookOpen size={16} />
                {source.publisher}
                {source.data.mock && <Badge value="mock">Demo</Badge>}
              </div>
              <h3>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                  <ArrowUpRight size={14} />
                </a>
              </h3>
              <p>
                {source.data.snippet.replaceAll(/<\/?untrusted_source>/g, "")}
              </p>
              <dl>
                <div>
                  <dt>Published</dt>
                  <dd>{date(source.published_at)}</dd>
                </div>
                <div>
                  <dt>Retrieved</dt>
                  <dd>{date(source.retrieved_at)}</dd>
                </div>
                <div>
                  <dt>Source ID</dt>
                  <dd className="mono">{source.id.slice(0, 8)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
