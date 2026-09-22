# factory_a_pkg — Factory-A Product Package

Self-contained copy of the Factory-A coding/verification engine, gathered into one folder for
productization (IDE extension). **Everything here was COPIED, not moved** — the live Factory-A system
(22-module PythonBrain, Spider-M, PAL, and any active build session) is untouched and still runs from
its original locations. This folder is safe to edit/delete without affecting them.

Verified self-contained: the package's own gate ran on its own example end-to-end —
`stage_tests/gate_runner.py` on a bundle of `examples/safe_stats/` → **8/8 tests, M8/Stage2/M7 PASS,
Final PASS, G-Score 1.0** (paths internal only).

## Layout & provenance (what came from where)

| In package | Copied from | What it is |
|---|---|---|
| `factory_core/` | `C:\Factory-A\factory_core\` | Laws/schemas (invariants master, reason codes master, canonical fields, authority matrix) |
| `stage_tests/` | `C:\Factory-A\stage_tests\` | **The GATE**: `gate_runner.py` + `m8/` + `stage2/` + `m7/` + `config/` + `aiel_t/` (incl. `adapter_registry.py` multi-language) + `gate_c/` (receipt builder) |
| `integrate.py`, `integrate_multi_m.py` | `C:\Factory-A\` | Pipeline drivers (bundle assembly → gate) |
| `prompts/` | `C:\Factory-A\orchestrator\` | AIEL roles & policy: `Master_prompt_trinity_m2.txt`, `FACTORY-A_FULL_PIPELINE_POLICY_v2.md`, `FACTORY_A_PRODUCTION_LINEBOOK.md` |
| `examples/safe_stats/` | `C:\Factory-A\product_demo\safe_stats\` | Worked demo: spec pack (5 files) + built package + 8 golden tests (domain-neutral) |
| `examples/trinity_m1/` | `C:\Factory-A\modules_dev\trinity_m1\` | A real module example (spec pack + AIEL-0/1/2/3 stages) so the AI has a concrete pattern to follow |
| `companion/ode/` | `C:\Factory-A\bridger_council\` | **ODE** ("AI Operation Desk") — the wow/signature layer. Lets the IDE AI reach other-vendor CLIs (V5), browsers/council (V7: Claude/GPT/Gemini/DeepSeek), web automation (V8), local Ollama (V6). Runs as a **separate desktop companion** (Tkinter + CDP — cannot live inside the VS Code extension sandbox); the extension talks to it. |

**Deliberately excluded** (and why): the 22 production modules (not needed — one example is enough for the AI to pattern-match), 60+ baseline zips & 34 decision receipts (artifacts, not engine), Spider-M / PAL / caches (separate workstreams), ODE `sessions/`/`artifacts/`/backups (runtime junk).

## How to run the gate (one command)
```
# from this folder — auto-bundles, generates manifest, runs M8+Stage2+M7
python run_gate.py examples/safe_stats --profile strict
# expect: VERDICT: PASS, 8/8 tests, M8/Stage2/M7 PASS

python run_gate.py <your-folder> --profile general   # for normal app code
```
`run_gate.py` is workspace-relative; set env `FACTORY_A_HOME` to relocate. License: set
`FACTORY_A_LICENSE_KEY` or drop a `license.key` here (absent = EVALUATION mode, still runs).

## Adaptation status (A–D DONE 2026-06-19)
- **A ✅** Hostname authority lock removed → `verify_license()` in `integrate.py` (env/`license.key`, eval-mode fallback, never aborts on machine identity)
- **B ✅** `C:\Factory-A` hardcode → `FACTORY_A_HOME` (env or script-relative) in `integrate.py` + `integrate_multi_m.py`
- **C ✅** `run_gate.py` — auto-generates `manifest.json` (module_inventory+graph from folder layout) + zips + runs the gate. One command, no hand-built zips.
- **D ✅** `profiles/general` + `profiles/strict` (gate config + `m8_invariants.yaml` + `LAWS.md` spec-block + neutral `reason_codes_template.yaml`). `general` = code may use I/O, tests must stay deterministic; `strict` = pure-logic, no network/time/random. `--profile` flag wired into `run_gate.py`.

## Multi-language (DONE 2026-06-19) — 7 languages
The gate is no longer Python-only. `stage_tests/gate_runner.py` Stage2/M5 dispatches by language
(`_run_test_suite`): Python uses the existing pytest path unchanged (zero regression); non-Python routes
through the AIEL-T adapter registry (`stage_tests/aiel_t/adapter_registry.py`) with **real test-count parsing**:

| Language | Test cmd | Verified |
|---|---|---|
| Python | pytest | live (8/8, `examples/safe_stats`) |
| JS/TS | node:test / npm test | **live (4/4, `examples/js_stats`)** |
| Go | go test | fixture |
| Rust | cargo test | fixture |
| Java | mvn/gradle test (JUnit) | fixture |
| C# | dotnet test | fixture |
| C++ | ctest | fixture |

(JS **and** TS are one Node adapter = the 66%-most-used family.) Windows-safe launcher `_winsafe` handles
`npm.cmd`. Every adapter's parser is proven by `stage_tests/aiel_t/adapter_selftest.py` (12 fixtures, pass+fail
each) — **ALL PASS**. New languages: copy `adapter_template.py`, register, and pass the self-test (see
`ADAPTER_GUIDE.md`). M7 replay is pytest-based → **skipped (honestly logged) for non-Python**; per-language replay is TODO.
```
python run_gate.py examples/js_stats --profile general    # Node live demo
python stage_tests/aiel_t/adapter_selftest.py             # prove all adapters parse correctly
```

## Anti-hallucination static gate + round guard (DONE 2026-06-20)
Built fresh in `stage_tests/static_checks/` (Joe-requested; principle existed, code didn't):
- **`hallucination_gate.py`** — AST "phantom name" detector: flags names USED but never
  defined/imported/builtin (the classic AI failure: invented variable / typo'd module / phantom API).
  Pure AST, deterministic, **0 LLM tokens**. Wired into `run_gate.py` as a **pre-gate** (fail-fast before
  the expensive full gate). Self-test: clean PASS, phantom-var FAIL, phantom-API FAIL — ALL PASS.
  Verified live: a module using `rate`/`offset_misspelled` (never defined) → bounced at pre-gate, 0 tokens,
  full gate not run; clean `safe_stats` → PASS + full gate still PASS (no regression).
- **`round_guard.py`** — fix-loop circuit breaker + token-burn meter: if the AIEL fix loop can't pass within
  N rounds (default 3), EJECT with `RC_SPEC_LIKELY_WRONG` ("the spec/logic is wrong, not the code — fix the
  spec") instead of brute-forcing/burning tokens. Tracks cumulative token burn. Self-test ALL PASS.
  (Reusable component; wire into the AIEL-0→3 orchestrator loop.)
```
python stage_tests/static_checks/hallucination_gate.py   # self-test
python stage_tests/static_checks/round_guard.py          # self-test
python run_gate.py <folder>   # runs hallucination pre-gate, then full gate
```

## VS Code extension shell + Benchmark (DONE 2026-06-20)
- **`vscode_extension/`** — installable extension MVP: commands "Verify Folder (full gate)" + "Check
  Hallucinated Names (fast)", output panel, settings (home/python/profile). Surfaces Verified ✓ / Blocked ✗,
  hides the machinery; drives `run_gate.py` as a subprocess. Validated: `node --check` + valid `package.json`.
  NOT yet live-tested in a VS Code host / published (needs `vsce package` + install). See its README.
- **`benchmark/bench_hallucination.py`** — reproducible labeled-corpus benchmark for the phantom-name gate:
  **precision 1.00 / recall 1.00 / accuracy 1.00 (n=10)**, honestly reporting the hard cases (star-import skip,
  semantic-out-of-scope). See `benchmark/BENCHMARK.md`. (End-to-end with-gate-vs-without AI-in-loop benchmark = TODO.)
- Also added `run_gate.py --halonly` (fast hallucination-only check, used by the extension).

## AIEL runner — pipeline orchestrator as a product component (DONE 2026-06-20)
**`aiel_runner.py`** — drives a **pluggable AI** through AIEL-0→3, runs the deterministic gate, and on
failure **bounces back to the right stage** with the reason, looping under `RoundGuard` (eject if the
spec/logic is the real problem). Turns "plug in the customer's AI → run the pipeline" from a manual demo
into a real component. The AI is any object with `.generate(stage, spec, files, feedback) -> {name: src}`
(wire to VS Code LM API / ODE channel / API); orchestration + gate + bounce + round-guard are
deterministic (0 trust in the AI). Self-test (mock AIs): fixing-AI → CERTIFIED in 2 rounds (phantom
caught → bounced to AIEL-2 → fixed → pass); stubborn-AI → EJECTED `RC_SPEC_LIKELY_WRONG` at round 3.
```
python aiel_runner.py   # self-test
```

## Still TODO (toward a sellable marketplace v1)
- Live-test + publish the VS Code extension (vsce package, VS Code host); inline diagnostics, status bar  ← **Joe handles publish**
- License-server backend (current `verify_license` is a stub) + subscription/billing
- Wire `aiel_runner`'s pluggable AI to a REAL backend (VS Code LM API / ODE channel) + its gate to full `run_gate`
- Stronger AI-in-loop benchmark (larger corpus); per-language M7 replay; Go/Rust/Java/C#/C++ live CI
