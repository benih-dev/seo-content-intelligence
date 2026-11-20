import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./theme.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { themeScript } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function boot(saved, dark = false, blocked = false) {
  const dataset = {};
  const listeners = {};
  const media = { matches: dark, addEventListener: (_, callback) => { listeners.media = callback; } };
  let stored = saved;
  vm.runInNewContext(themeScript, {
    document: { documentElement: { dataset } },
    window: { matchMedia: () => media, addEventListener: (name, callback) => { listeners[name] = callback; } },
    localStorage: {
      getItem: () => { if (blocked) throw Error("blocked"); return stored; },
      setItem: (_, value) => { if (blocked) throw Error("blocked"); stored = value; },
    },
  });
  return { dataset, listeners, media, stored: () => stored };
}

test("pre-paint theme defaults to system and tolerates empty/invalid/blocked storage", () => {
  for (const saved of [null, "", "invalid"]) {
    for (const dark of [false, true]) {
      const { dataset } = boot(saved, dark);
      assert.equal(dataset.theme, dark ? "dark" : "light");
      assert.equal(dataset.themePreference, "system");
    }
  }
  assert.equal(boot(null, true, true).dataset.theme, "dark");
});

test("explicit preferences persist, override OS, and restore on reload", () => {
  const state = boot("light", true);
  assert.equal(state.dataset.theme, "light");
  state.listeners["seoci-theme-change"]({ detail: "dark" });
  assert.equal(state.dataset.theme, "dark");
  assert.equal(state.stored(), "dark");
  assert.equal(boot(state.stored()).dataset.theme, "dark");
  state.media.matches = false;
  state.listeners.media();
  assert.equal(state.dataset.theme, "dark");
  state.listeners["seoci-theme-change"]({ detail: "system" });
  assert.equal(state.dataset.theme, "light");
  state.media.matches = true;
  state.listeners.media();
  assert.equal(state.dataset.theme, "dark");
});

test("storage changes sync tabs and unavailable storage does not block selection", () => {
  const state = boot("dark");
  state.listeners.storage({ key: "seoci-theme", newValue: "light" });
  assert.equal(state.dataset.theme, "light");
  state.listeners.storage({ key: null, newValue: null });
  assert.equal(state.dataset.themePreference, "system");
  const blocked = boot(null, false, true);
  blocked.listeners["seoci-theme-change"]({ detail: "dark" });
  assert.equal(blocked.dataset.theme, "dark");
});

test("theme text tokens meet WCAG AA contrast on their surfaces", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const luminance = (hex) => {
    const values = hex.match(/\w\w/g).map(v => parseInt(v, 16) / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
  };
  let tokens = {};
  for (const block of css.matchAll(/:root(?:\[data-theme="dark"\])?\s*\{([^}]+)\}/g)) {
    tokens = { ...tokens, ...Object.fromEntries([...block[1].matchAll(/--([\w-]+): #([a-f0-9]{6});/g)].map(m => [m[1], m[2]])) };
    for (const [fg, bg] of [
      ...["text", "muted", "accent"].flatMap(fg => ["bg", "surface", "subtle"].map(bg => [fg, bg])),
      ["on-accent", "accent-fill"], ["accent", "blue-bg"],
      ...["success", "warning", "danger", "purple"].map(name => [name, `${name}-bg`]),
    ]) {
      const values = [luminance(tokens[fg]), luminance(tokens[bg])].sort((a, b) => b - a);
      assert.ok((values[0] + 0.05) / (values[1] + 0.05) >= 4.5, `${fg} on ${bg}`);
    }
    const border = luminance(tokens["control-line"]);
    const surface = luminance(tokens.surface);
    assert.ok((Math.max(border, surface) + 0.05) / (Math.min(border, surface) + 0.05) >= 3, "control boundary contrast");
  }
});
