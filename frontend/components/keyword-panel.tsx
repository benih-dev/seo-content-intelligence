"use client";
import { useState } from "react";
import { ArrowUpRight, Check, Info } from "lucide-react";
import { date, label, percent } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Badge, Empty, Panel } from "./ui";

export type Command = (
  path: string,
  body?: unknown,
  method?: string,
) => Promise<void>;
export function KeywordPanel({
  run,
  command,
  busy,
}: {
  run: Run;
  command: Command;
  busy: boolean;
}) {
  const [selected, setSelected] = useState(
    run.keywords.find((k) => k.selected)?.keyword || run.primary_keyword,
  );
  const candidate =
    run.keywords.find((k) => k.keyword === selected) || run.keywords[0];
  const [intent, setIntent] = useState(candidate?.intent || "informational");
  if (!candidate)
    return (
      <Empty title="Research is taking shape">
        Keyword data and a timestamped SERP snapshot will appear when the worker
        finishes.
      </Empty>
    );
  const snapshot = run.serp_snapshots.find(
    (s) => s.id === candidate.data.serp_snapshot_id,
  );
  const metric = candidate.data.metrics;
  const strategy = run.artifacts.find((x) => x.stage === "strategy");
  const warnings = (strategy?.data.overlap_warnings || []) as {
    url: string;
    reason: string;
    recommendation: string;
  }[];
  const atGate = run.state === "keyword_review";
  return (
    <div className="panel-stack">
      {atGate && (
        <div className="gate-banner">
          <div className="gate-number">01</div>
          <div>
            <strong>A good article starts with the right keyword.</strong>
            <p>
              Review the search landscape, confirm intent, and choose your
              opportunity.
            </p>
          </div>
          <span className="gate-pill">YOUR REVIEW</span>
        </div>
      )}
      {run.mode === "discovery" && (
        <Panel title="Choose an opportunity" eyebrow="DISCOVERY SHORTLIST">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Select keyword</th>
                  <th>Opportunity</th>
                  <th>Confidence</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {run.keywords.map((k) => (
                  <tr key={k.id}>
                    <td>
                      <label className="inline-label">
                        <input
                          type="radio"
                          name="keyword"
                          checked={selected === k.keyword}
                          disabled={!atGate || busy}
                          onChange={() => {
                            setSelected(k.keyword);
                            setIntent(k.intent);
                          }}
                        />
                        {k.keyword}
                      </label>
                    </td>
                    <td>{k.score} / 100</td>
                    <td>{percent(k.confidence)}</td>
                    <td>{k.data.metrics.volume ?? "Unavailable"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <div className="two-column keyword-columns">
        <Panel
          title="Keyword intelligence"
          eyebrow="SEARCH OPPORTUNITY"
          aside={
            <Badge value={metric.provider}>
              {metric.provider === "mock" ? "Demo data" : metric.provider}
            </Badge>
          }
        >
          <h3 className="keyword-title">{candidate.keyword}</h3>
          <div className="metric-grid">
            <div>
              <small>Search volume</small>
              <strong>
                {metric.volume === null ? (
                  <span className="unavailable">Unavailable</span>
                ) : (
                  metric.volume.toLocaleString()
                )}
              </strong>
            </div>
            <div>
              <small>Competition</small>
              <strong className="unavailable">
                {metric.competition ?? "Unavailable"}
              </strong>
            </div>
            <div>
              <small>Opportunity score</small>
              <strong>
                {candidate.score}
                <span className="metric-denominator">/100</span>
              </strong>
            </div>
            <div>
              <small>Data confidence</small>
              <strong>{percent(candidate.confidence)}</strong>
            </div>
          </div>
          <div className="provenance">
            <span>
              Provider <b>{metric.provider}</b>
            </span>
            <span>
              Locale <b>{run.locale}</b>
            </span>
            <span>
              Captured <b>{date(metric.captured_at)}</b>
            </span>
            <span>
              Period <b>{metric.period}</b>
            </span>
          </div>
          <div className="notice subtle">
            <Info size={16} />
            <p>
              Missing metrics stay unavailable. Opportunity is an internal
              editorial aid, never a ranking prediction.
            </p>
          </div>
        </Panel>
        <Panel title="Search intent" eyebrow="INTERPRETATION, NOT FACT">
          <div className="intent-summary">
            <span className="intent-icon">↗</span>
            <div>
              <h3>{label(candidate.intent)}</h3>
              <small>
                {percent(candidate.data.intent.confidence)} model confidence
              </small>
            </div>
          </div>
          <p className="body-copy">{candidate.data.intent.reason}</p>
          <label>
            Final intent / override
            <select
              value={intent}
              disabled={!atGate || busy}
              onChange={(e) => setIntent(e.target.value)}
            >
              {[
                ...new Set([
                  candidate.intent,
                  "informational",
                  "commercial",
                  "transactional",
                  "navigational",
                  "mixed",
                ]),
              ].map((x) => (
                <option key={x} value={x}>
                  {label(x)}
                </option>
              ))}
            </select>
          </label>
          <small className="field-note">
            Your final choice is recorded and used in the content brief.
          </small>
        </Panel>
      </div>
      <Panel
        title="Why this opportunity?"
        eyebrow="TRANSPARENT SCORING"
        aside={
          <span className="muted">Six dimensions · weighted assessment</span>
        }
      >
        <div className="score-list">
          {Object.entries(candidate.data.opportunity.dimensions).map(
            ([key, d]) => (
              <div className="score-row" key={key}>
                <div>
                  <strong>{label(key)}</strong>
                  <span className="score-weight">
                    {percent(d.weight)} weight
                  </span>
                  <p>{d.reason}</p>
                </div>
                <div className="score-visual">
                  <span className="score-track">
                    <span style={{ width: `${d.score || 0}%` }} />
                  </span>
                  <strong>{d.score ?? "—"}</strong>
                </div>
                <span className="confidence">
                  {percent(d.confidence)} confidence
                </span>
              </div>
            ),
          )}
        </div>
      </Panel>
      <Panel
        title="Search landscape"
        eyebrow="SERP SNAPSHOT"
        aside={
          snapshot && (
            <span className="muted">
              {snapshot.provider} · {snapshot.data.device} ·{" "}
              {date(snapshot.data.captured_at)}
            </span>
          )
        }
      >
        {snapshot ? (
          <>
            <p className="panel-description">
              Results for “{snapshot.query}” in {snapshot.locale}.
              {snapshot.data.mock &&
                " Offline example results — not live rankings."}
            </p>
            <div className="serp-list">
              {snapshot.data.results.map((result) => (
                <div className="serp-result" key={result.url}>
                  <span className="rank">
                    {String(result.rank).padStart(2, "0")}
                  </span>
                  <div>
                    <a href={result.url} target="_blank" rel="noreferrer">
                      {result.title}
                      <ArrowUpRight size={14} />
                    </a>
                    <small>{result.url}</small>
                    <p>{result.snippet}</p>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <Empty title="No SERP snapshot available" />
        )}
      </Panel>
      <Panel title="Site fit & overlap" eyebrow="MAKE SPACE FOR ORIGINAL VALUE">
        {strategy ? (
          <>
            <h3>{String(strategy.data.angle)}</h3>
            <p className="body-copy">{String(strategy.data.rationale)}</p>
            <p className="body-copy">{String(strategy.data.differentiation)}</p>
            {warnings.length ? (
              warnings.map((w) => (
                <div className="notice warning" key={w.url}>
                  <Info size={18} />
                  <div>
                    <strong>Potential cannibalization</strong>
                    <p>{w.reason}</p>
                    <a href={w.url} target="_blank" rel="noreferrer">
                      {w.url}
                    </a>
                    <p>
                      Consider updating this existing article or differentiating
                      the angle.
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="notice success">
                <Check size={16} />
                No overlapping titles or slugs found in the current inventory.
              </div>
            )}
            {strategy.data.ymyl === true && (
              <div className="notice warning">
                Expert review required — this topic may affect high-impact
                decisions.
              </div>
            )}
          </>
        ) : (
          <p className="body-copy">
            Site-fit strategy and overlap warnings are generated after keyword
            approval, before you approve the brief. Existing content inventory
            is used to identify potential cannibalization.
          </p>
        )}
      </Panel>
      {atGate && (
        <div className="approval-bar">
          <div>
            <strong>Ready to develop this opportunity?</strong>
            <p>Next: site-fit strategy and an editable content brief.</p>
          </div>
          <button
            className="button primary"
            disabled={busy}
            onClick={() =>
              command("approve", {
                stage: "keyword",
                payload: { keyword: selected, intent },
              })
            }
          >
            <Check size={16} />
            Approve keyword
          </button>
        </div>
      )}
    </div>
  );
}
