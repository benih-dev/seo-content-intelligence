import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./keyword-review.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { readReviewChoice, saveReviewChoice, clearReviewChoice } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const candidate = (keyword, score = 50) => ({ keyword, score, intent: "informational", selected: false });
const run = { id: "one", state: "keyword_review", primary_keyword: "seed", keywords: [candidate("first"), candidate("best", 80)] };
function storage() {
  const data = new Map();
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: (key) => data.delete(key) };
}

test("defaults to actual highest score, seed when present, approved choice first", () => {
  assert.equal(readReviewChoice(run).keyword, "best");
  const withSeed = { ...run, keywords: [...run.keywords, candidate("seed")] };
  assert.equal(readReviewChoice(withSeed).keyword, "seed");
  assert.equal(readReviewChoice({ ...withSeed, keywords: [{ ...candidate("approved"), selected: true }, ...withSeed.keywords] }).keyword, "approved");
});

test("selection and override survive remount/reload reads, isolated by run", () => {
  const local = storage();
  const choice = { keyword: "first", intent: "commercial" };
  saveReviewChoice(run.id, choice, local);
  assert.deepEqual(readReviewChoice(run, local), choice);
  assert.deepEqual(readReviewChoice(JSON.parse(JSON.stringify(run)), local), choice);
  assert.equal(readReviewChoice({ ...run, id: "two" }, local).keyword, "best");
  clearReviewChoice(run.id, local);
  assert.equal(readReviewChoice(run, local).keyword, "best");
});

test("approved records supersede drafts", () => {
  const local = storage();
  saveReviewChoice(run.id, { keyword: "first", intent: "commercial" }, local);
  const approved = { ...run, state: "brief_review", keywords: [{ ...candidate("best"), selected: true, intent: "transactional" }] };
  assert.deepEqual(readReviewChoice(approved, local), { keyword: "best", intent: "transactional" });
});

test("invalid, obsolete, empty and inaccessible storage fall back safely", () => {
  const local = storage();
  for (const value of ["not json", "null", '{"keyword":"missing","intent":"commercial"}', '{"keyword":"first","intent":"invalid"}']) {
    local.setItem("seoci:keyword-review:one", value);
    assert.equal(readReviewChoice(run, local).keyword, "best");
  }
  const blocked = { getItem() { throw Error("blocked"); }, setItem() { throw Error("blocked"); }, removeItem() { throw Error("blocked"); } };
  assert.equal(readReviewChoice(run, blocked).keyword, "best");
  assert.doesNotThrow(() => saveReviewChoice(run.id, { keyword: "first", intent: "mixed" }, blocked));
  assert.doesNotThrow(() => clearReviewChoice(run.id, blocked));
  assert.deepEqual(readReviewChoice({ ...run, keywords: [] }, local), { keyword: "", intent: "informational" });
});
