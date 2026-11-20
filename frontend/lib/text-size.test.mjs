import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = readFileSync(new URL("./text-size.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { textSizeScript } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function boot(saved, blocked = false) {
  const dataset = {};
  const listeners = {};
  let stored = saved;
  vm.runInNewContext(textSizeScript, {
    document: { documentElement: { dataset } },
    window: { addEventListener: (name, callback) => { listeners[name] = callback; } },
    localStorage: {
      getItem: () => { if (blocked) throw Error("blocked"); return stored; },
      setItem: (_, value) => { if (blocked) throw Error("blocked"); stored = value; },
    },
  });
  return { dataset, listeners, stored: () => stored };
}

test("pre-paint text size defaults to Normal with empty, invalid or blocked storage", () => {
  for (const saved of [null, "", "invalid"]) assert.equal(boot(saved).dataset.textSize, "normal");
  assert.equal(boot("large", true).dataset.textSize, "normal");
  const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
  assert.ok(layout.indexOf("__html: textSizeScript") < layout.indexOf("<body>"));
  assert.match(layout, /<html[^>]*suppressHydrationWarning/);
});

test("Small, Normal and Large persist and restore on reload", () => {
  const state = boot("large");
  assert.equal(state.dataset.textSize, "large");
  for (const choice of ["small", "normal", "large"]) {
    state.listeners["seoci-text-size-change"]({ detail: choice });
    assert.equal(state.dataset.textSize, choice);
    assert.equal(state.stored(), choice);
    assert.equal(boot(state.stored()).dataset.textSize, choice);
  }
  state.listeners["seoci-text-size-change"]({ detail: "invalid" });
  assert.equal(state.dataset.textSize, "normal");
});

test("storage events sync tabs and clearing storage restores Normal", () => {
  const state = boot("normal");
  state.listeners.storage({ key: "seoci-text-size", newValue: "large" });
  assert.equal(state.dataset.textSize, "large");
  state.listeners.storage({ key: "seoci-theme", newValue: "light" });
  assert.equal(state.dataset.textSize, "large");
  state.listeners.storage({ key: "seoci-text-size", newValue: "invalid" });
  assert.equal(state.dataset.textSize, "normal");
  state.listeners.storage({ key: "seoci-text-size", newValue: "small" });
  state.listeners.storage({ key: null, newValue: null });
  assert.equal(state.dataset.textSize, "normal");
  const blocked = boot(null, true);
  blocked.listeners["seoci-text-size-change"]({ detail: "large" });
  assert.equal(blocked.dataset.textSize, "large");
});

test("native text size selector is labelled and is present on public and signed-in pages", () => {
  const source = readFileSync(new URL("../components/text-size-select.tsx", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  } });
  const compiled = { exports: {} };
  new Function("require", "module", "exports", outputText)(createRequire(import.meta.url), compiled, compiled.exports);
  const html = renderToStaticMarkup(createElement(compiled.exports.TextSizeSelect));
  assert.match(html, /<select[^>]*aria-label="Text size"/);
  for (const choice of ["small", "normal", "large"]) assert.ok(html.includes(`value="${choice}"`));
  assert.match(html, /<option value="normal" selected="">/);
  const shell = readFileSync(new URL("../components/shell.tsx", import.meta.url), "utf8");
  assert.equal([...shell.matchAll(/<TextSizeSelect\s*\/>/g)].length, 2);
});

test("typography uses readable rem sizes that follow the root text size", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.doesNotMatch(css, /font-size:\s*[\d.]+px/);
  const sizes = [...css.matchAll(/font-size:\s*([\d.]+)rem/g)].map(match => Number(match[1]));
  assert.ok(sizes.length > 100);
  assert.ok(sizes.every(size => size >= 13 / 16));
  assert.match(css, /body\s*\{[^}]*font-size: 1rem;/);
  assert.match(css, /:root\s*\{[^}]*font-size: 100%;/);
  assert.match(css, /:root\[data-text-size="small"\]\s*\{\s*font-size: 87\.5%;/);
  assert.match(css, /:root\[data-text-size="large"\]\s*\{\s*font-size: 112\.5%;/);
});

test("sidebar allows vertical scrolling so large text cannot strand the footer", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.sidebar\s*\{[^}]*overflow-y: auto;/);
});
