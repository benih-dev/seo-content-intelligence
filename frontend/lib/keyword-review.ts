type Candidate = { keyword: string; intent: string; score: number; selected: boolean };
type ReviewRun = { id: string; state: string; primary_keyword: string; keywords: Candidate[] };
type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
export type ReviewChoice = { keyword: string; intent: string };
const intents = new Set(["informational", "commercial", "transactional", "navigational", "mixed"]);
const key = (id: string) => `seoci:keyword-review:${id}`;

export function reviewStorage(): Storage | undefined {
  try { return typeof window === "undefined" ? undefined : window.localStorage; } catch { return undefined; }
}

export function readReviewChoice(run: ReviewRun, storage?: Storage): ReviewChoice {
  const candidate = run.keywords.find((k) => k.selected) ||
    run.keywords.find((k) => k.keyword === run.primary_keyword) ||
    [...run.keywords].sort((a, b) => b.score - a.score)[0];
  const fallback = { keyword: candidate?.keyword || "", intent: candidate?.intent || "informational" };
  if (run.state !== "keyword_review") return fallback;
  try {
    const saved = JSON.parse(storage?.getItem(key(run.id)) || "null");
    if (saved && run.keywords.some((k) => k.keyword === saved.keyword) && intents.has(saved.intent)) {
      return { keyword: saved.keyword, intent: saved.intent };
    }
  } catch { /* Storage may be unavailable or contain an obsolete draft. */ }
  return fallback;
}

export function saveReviewChoice(id: string, choice: ReviewChoice, storage?: Storage) {
  try { storage?.setItem(key(id), JSON.stringify(choice)); } catch { /* Storage is optional. */ }
}

export function clearReviewChoice(id: string, storage?: Storage) {
  try { storage?.removeItem(key(id)); } catch { /* Storage is optional. */ }
}
