import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./settings.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { settingsPatch, secretStatus } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const initial = {
  llm_model: "", llm_api_base: "", serp_provider: "mock", dataforseo_login: "", github_api_url: "https://api.github.com",
  llm_api_key: { configured: true, source: "db" }, dataforseo_password: { configured: false, source: "none" },
  github_token: { configured: true, source: "env" }, modes: { llm: "mock", serp: "mock" },
};

test("unchanged values and empty secret inputs produce no updates", () => {
  assert.deepEqual(settingsPatch(initial, initial, {}), {});
  assert.deepEqual(settingsPatch(initial, initial, { llm_api_key: "", github_token: "" }), {});
});

test("only edited public fields and explicit replacement/clear are submitted", () => {
  assert.deepEqual(settingsPatch(initial, { ...initial, llm_model: "openai/demo" }, { llm_api_key: "dummy-key", github_token: null }), {
    llm_model: "openai/demo", llm_api_key: "dummy-key", github_token: null,
  });
  assert.deepEqual(settingsPatch(initial, initial, { unknown: "never-send" }), {});
});

test("secret badges expose status and source, not values", () => {
  assert.equal(secretStatus(initial.llm_api_key), "Configured (saved in app)");
  assert.equal(secretStatus(initial.github_token), "Configured (from environment)");
  assert.equal(secretStatus(initial.dataforseo_password), "Not set");
});

test("a failed save retains pending credentials and clears them only after a successful retry", async () => {
  const page = readFileSync(new URL("../app/settings/page.tsx", import.meta.url), "utf8");
  const file = ts.createSourceFile("page.tsx", page, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let handler;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === "save") handler = node.getText(file);
    ts.forEachChild(node, visit);
  }
  visit(file);
  assert.ok(handler, "Settings save handler exists");
  const { outputText } = ts.transpileModule(handler, { compilerOptions: { target: ts.ScriptTarget.ES2022 } });
  const state = { saved: initial, values: { ...initial, llm_api_base: "invalid" },
    secrets: { llm_api_key: "dummy-pending-key", dataforseo_password: "dummy-pending-password", github_token: null } };
  const pending = { ...state.secrets };
  const requests = [];
  let fail = true;
  const api = async (path, body, method) => {
    requests.push({ path, body, method });
    if (fail) throw new Error("Invalid URL");
    return { ...initial, llm_api_base: state.values.llm_api_base };
  };
  const names = ["saved", "values", "secrets", "api", "settingsPatch", "setSaved", "setValues", "setSecrets", "setError", "setMessage", "setBusy"];
  const invoke = async () => {
    const save = new Function(...names, `${outputText};return save;`)(
      state.saved, state.values, state.secrets, api, settingsPatch,
      ...["saved", "values", "secrets", "error", "message", "busy"].map(key => value => { state[key] = value; }),
    );
    await save({ preventDefault() {} });
  };
  await invoke();
  assert.deepEqual(state.secrets, pending);
  assert.match(state.error, /could not be saved/);
  assert.equal(state.busy, false);
  state.values = { ...state.values, llm_api_base: "https://llm.example/v1" };
  fail = false;
  await invoke();
  assert.deepEqual(requests[1], { path: "/settings", method: "PUT", body: { llm_api_base: "https://llm.example/v1", ...pending } });
  assert.deepEqual(state.secrets, {});
  assert.match(state.message, /Settings saved/);
  assert.equal(state.busy, false);
});
