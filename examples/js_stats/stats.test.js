"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { summarize } = require("./safe_stats.js");

test("summary of 1..5", () => {
  const s = summarize([1, 2, 3, 4, 5]);
  assert.strictEqual(s.count, 5);
  assert.strictEqual(s.sum, 15);
  assert.strictEqual(s.mean, 3);
  assert.strictEqual(s.min, 1);
  assert.strictEqual(s.max, 5);
});

test("single value", () => {
  const s = summarize([42]);
  assert.strictEqual(s.mean, 42);
});

test("asymmetric mean (oracle)", () => {
  // mean=3, median=2 — a median-bug would fail here
  assert.strictEqual(summarize([1, 2, 6]).mean, 3);
});

test("rejects empty", () => {
  assert.throws(() => summarize([]), /EMPTY_VALUES/);
});
