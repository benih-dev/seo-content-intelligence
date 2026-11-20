import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

function load(path) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } });
  const compiled = { exports: {} }, require = createRequire(import.meta.url);
  const imports = name => name === "next/link" ? { default: ({ children, ...props }) => createElement("a", props, children) }
    : name === "@/lib/api" ? { api() { throw Error("Unexpected request during render"); } } : require(name);
  new Function("require", "module", "exports", outputText)(imports, compiled, compiled.exports);
  return compiled.exports;
}

test("logs query supports empty filters and encodes run/level filters", () => {
  const { logsPath } = load("./diagnostics.ts");
  assert.equal(logsPath("", ""), "/logs");
  assert.equal(logsPath(" run-id ", "error"), "/logs?run_id=run-id&level=error");
  assert.equal(logsPath("a&b", ""), "/logs?run_id=a%26b");
});

test("run errors render classification, hint, attempts and a filtered Logs link with legacy fallback", () => {
  const { RunError } = load("../components/run-error.tsx");
  const html = renderToStaticMarkup(createElement(RunError, { runId: "run-id", message: "Legacy error", details: {
    category: "auth", message: "LLM (HTTP 401): Authentication failed", hint: "Check the API key in Settings.",
    stage: "keyword_research", attempt: 2, timestamp: "2026-01-01",
  } }));
  for (const value of ['role="alert"', "HTTP 401", "Check the API key", "keyword_research", "Attempt 2", "/logs?run_id=run-id"]) assert.ok(html.includes(value));
  const legacy = renderToStaticMarkup(createElement(RunError, { runId: "old", message: "Legacy error" }));
  assert.ok(legacy.includes("Legacy error"));
});

test("connection results have accessible empty, success and error states", () => {
  const { ConnectionResultNotice, ConnectionTest } = load("../components/connection-test.tsx");
  const empty = renderToStaticMarkup(createElement(ConnectionResultNotice));
  assert.ok(empty.includes('role="status"') && !empty.includes("notice"));
  for (const ok of [true, false]) {
    const html = renderToStaticMarkup(createElement(ConnectionResultNotice, { result: { ok, message: "Connection result", hint: "Actionable hint" } }));
    assert.ok(html.includes(ok ? "success" : "error"));
    assert.ok(html.includes("Connection result") && html.includes("Actionable hint"));
  }
  for (const kind of ["llm", "serp", "keyword"]) {
    const html = renderToStaticMarkup(createElement(ConnectionTest, { kind }));
    assert.ok(html.includes(`aria-label="Test ${kind.toUpperCase()} connection"`));
    assert.ok(html.includes('type="button"') && html.includes("saved settings only"));
  }
});
