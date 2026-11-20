import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { api, authPath } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("authentication redirects and cookie forwarding", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const redirects = [];
  const requests = [];
  globalThis.window = { location: { replace: path => redirects.push(path) } };
  let setup = true;
  globalThis.fetch = async (path, options) => {
    requests.push({ path, options });
    return { status: 401, ok: false, json: async () => ({ detail: "Authentication required", setup_required: setup }) };
  };
  try {
    assert.equal(authPath(true), "/setup");
    assert.equal(authPath(false), "/login");
    await assert.rejects(api("/projects"), /Authentication required/);
    setup = false;
    await assert.rejects(api("/settings"), /Authentication required/);
    await assert.rejects(api("/auth/login", { username: "owner", password: "dummy-password" }), /Authentication required/);
    assert.deepEqual(redirects, ["/setup", "/login"]);
    assert.ok(requests.every(({ options }) => options.credentials === "same-origin"));
    assert.equal(requests[2].options.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
  }
});
