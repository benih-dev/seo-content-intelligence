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
