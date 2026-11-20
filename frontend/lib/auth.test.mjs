import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = readFileSync(new URL("./api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { api, authPath } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("server-rendered login and setup forms POST to fixed paths before hydration", () => {
  const source = readFileSync(new URL("../components/auth-form.tsx", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  } });
  const require = createRequire(import.meta.url);
  const compiled = { exports: {} };
  const load = name => {
    if (name === "next/navigation") return { useRouter: () => ({ replace() {} }) };
    if (name === "@/lib/api") return { api() { throw Error("No API calls during server render"); } };
    if (name === "@/components/ui") return {
      Panel: ({ children }) => createElement("section", null, children), ErrorNotice: () => null,
    };
    return require(name);
  };
  new Function("require", "module", "exports", outputText)(load, compiled, compiled.exports);
  for (const setup of [false, true]) {
    const html = renderToStaticMarkup(createElement(compiled.exports.AuthForm, { setup }));
    const form = html.match(/<form\b[^>]*>/)?.[0];
    assert.ok(form);
    assert.match(form, /method="post"/);
    assert.ok(form.includes(`action="${setup ? "/setup" : "/login"}"`));
    assert.match(html, /name="username"/);
    assert.match(html, /name="password"/);
  }
});

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
