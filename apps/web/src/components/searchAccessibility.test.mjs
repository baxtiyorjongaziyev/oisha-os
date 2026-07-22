import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { clearSearchQuery } from "./searchAccessibility.mjs";

test("clears the query before restoring input focus", () => {
  const events = [];

  clearSearchQuery((value) => events.push(["query", value]), {
    focus: () => events.push(["focus"])
  });

  assert.deepEqual(events, [["query", ""], ["focus"]]);
});

test("clears safely when the input is unavailable", () => {
  let query = "old query";

  clearSearchQuery((value) => {
    query = value;
  }, null);

  assert.equal(query, "");
});

test("keeps the clear control named, semantic, and ref-based", () => {
  const headerSource = readFileSync(new URL("./Header.tsx", import.meta.url), "utf8");
  const clearLabelIndex = headerSource.indexOf('aria-label="Qidiruvni tozalash"');
  const clearButtonStart = headerSource.lastIndexOf("<button", clearLabelIndex);
  const clearButtonMarkup = headerSource.slice(clearButtonStart, clearLabelIndex);

  assert.notEqual(clearLabelIndex, -1);
  assert.notEqual(clearButtonStart, -1);
  assert.match(clearButtonMarkup, /type="button"/);
  assert.match(clearButtonMarkup, /clearSearchQuery\(setSearchQuery, searchInputRef\.current\)/);
  assert.match(headerSource, /aria-label="Global qidiruvni ochish"/);
  assert.match(headerSource, /ref=\{searchInputRef\}/);
  assert.doesNotMatch(headerSource, /document\.getElementById/);
});
