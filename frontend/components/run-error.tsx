import Link from "next/link";

export interface RunErrorDetails {
  category: string;
  message: string;
  hint: string;
  stage: string;
  timestamp: string;
  attempt: number;
}

export function RunError({ runId, message, details }: { runId: string; message: string; details?: RunErrorDetails | null }) {
  return <div className="notice error" role="alert"><div>
    <strong>Run stopped: {details?.message || message}</strong>
    {details && <><p>{details.hint}</p><small>{details.category} · Stage: {details.stage} · Attempt {details.attempt} · {details.timestamp}</small></>}
    <p><Link href={`/logs?run_id=${encodeURIComponent(runId)}`}>View logs for this run</Link>. Fix the settings, then use Retry run above.</p>
  </div></div>;
}
