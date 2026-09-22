# Factory-A Benchmark (reproducible, honest)

The indie credibility asset: instead of a FAANG pedigree, let a skeptic **reproduce the numbers**.
Everything here is deterministic (0 tokens) and states what it does NOT measure.

## bench_hallucination.py — phantom-name detection
Measures the static anti-hallucination gate against a **labeled corpus** (code + ground-truth
"hallucinated? yes/no"). Reports TP/FP/TN/FN + precision/recall/accuracy.

```bash
python bench_hallucination.py
```

**Current result (n=10):** precision 1.00 · recall 1.00 · accuracy 1.00.

The corpus deliberately includes the hard cases and the result reports them honestly:
- `star_import_skipped` — `from x import *` hides names → gate SKIPS (won't false-alarm on valid code). Trade-off: phantom names inside a star-import module go undetected.
- `semantic_silent_out_of_scope` — median-mislabelled-as-mean uses only valid names → correctly NOT flagged. **Semantic correctness is the tests' job, not this gate.**

**Scope / honesty:** Python only; phantom-NAME detection (not a full type/scope checker). This benchmark
measures ONE gate (static hallucination). It does NOT yet measure the full pipeline's end-to-end
"hallucination-at-scale" reduction with a real AI in the loop — that requires an AI-in-loop experiment
(with-gate vs without-gate on real multi-module tasks) and is the next benchmark to build. Do not
over-claim from this number: it proves the static phantom-name gate is accurate on a labeled corpus,
nothing more.

## bench_endtoend.py — defects shipped: with-gate vs without (headline)
Runs a labeled set of tiny modules under three SHIP policies (actually executes the hallucination
gate + pytest):
- **TRUST** (≈ "AI proposes, accept" / Cursor-style) — ship if syntactically valid
- **CI_TESTS** (≈ ordinary CI) — ship if tests pass
- **FACTORY_A** — ship only if hallucination-gate PASS AND tests pass

```bash
python bench_endtoend.py
```
**Current result (4 defect classes): escape rate — TRUST 100% · CI_TESTS 50% · FACTORY_A 25%.**
Factory-A halves CI's escape rate (blocks an untested phantom-name defect CI ships). **Honest:** Factory-A
STILL ships `semantic_silent_weak_test` (median-as-mean whose test only checks a symmetric input) — the gate
is only as strong as the test, so the lever is spec/test quality. Tiny illustrative corpus; reproducible.

### What KPI does each number help? (the "so what")
| Benchmark metric | Buyer KPI | Why it matters |
|---|---|---|
| Escape rate ↓ (25% vs CI 50%) | **Production defect / incident rate** | fewer outages, less firefighting — the core "reliability at scale" sell |
| Caught pre-merge (at gate) | **Rework cost / debug time** | a bug caught at the gate is ~10–100× cheaper than in prod |
| Gate = 0 tokens + RoundGuard eject | **AI COGS / gross margin** | verification adds ~no token cost; hopeless specs ejected (bounded burn) |
| Phantom-name detection | **Hallucination rate** | the headline differentiator vs Copilot/Cursor |
| Replayable receipt (capability) | **Audit/compliance pass** | unlocks regulated buyers (finance/medical/safety) |

## TODO (stronger version)
- **AI-in-loop**: a real model builds a multi-module project twice (gate on/off), measure shipped-defect
  rate on a larger corpus. Must be fair (same model/prompts/tasks). The current bench is deterministic and
  policy-level — the AI-in-loop version adds external validity but needs a controlled experiment.
