import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./project-url.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { normalizeWebsiteUrl } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("normalizes website URLs without losing a case-sensitive base path", () => {
  for (const [input, expected] of [
    ["https://example.com/blog", "https://example.com/blog"],
    [" https://EXAMPLE.com/Blog/ ", "https://example.com/Blog"],
    ["example.com/blog/", "https://example.com/blog"],
    ["https://example.com/", "https://example.com"],
    ["https://example.com/blog?ref=setup#intro", "https://example.com/blog"],
  ]) assert.equal(normalizeWebsiteUrl(input), expected);
});

test("rejects empty, invalid, non-web, credential-bearing or whitespace URLs", () => {
  for (const input of ["", "   ", "https://", "ftp://example.com/blog", "https://user:pass@example.com/blog", "https://example.com/my blog"]) {
    assert.throws(() => normalizeWebsiteUrl(input), /Enter a website domain/);
  }
});
