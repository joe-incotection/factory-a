"use strict";

/**
 * Deterministic numeric summary (Node mirror of the SAFE_STATS example).
 * No I/O, no clock, no randomness.
 * @param {number[]} values non-empty array of finite numbers
 * @returns {{count:number,sum:number,mean:number,min:number,max:number}}
 */
function summarize(values) {
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error("SAFE_STATS_EMPTY_VALUES");
  }
  let sum = 0;
  let min = Infinity;
  let max = -Infinity;
  for (const v of values) {
    if (typeof v !== "number" || !Number.isFinite(v)) {
      throw new Error("SAFE_STATS_NAN_INF_DETECTED");
    }
    sum += v;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return { count: values.length, sum, mean: sum / values.length, min, max };
}

module.exports = { summarize };
