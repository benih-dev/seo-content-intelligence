export function logsPath(runId: string, level: string) {
  const query = new URLSearchParams();
  if (runId.trim()) query.set("run_id", runId.trim());
  if (level) query.set("level", level);
  return `/logs${query.size ? `?${query}` : ""}`;
}
