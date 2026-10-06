# Factory-A — VS Code Extension (shell / MVP)

**AI coding that doesn't fall apart at scale.** Every change is *verified, not trusted*: it must
pass a deterministic gate (no hallucinated names → tests 100% → replay-deterministic) before it
ships. You see **Verified ✓ / Blocked ✗** + a plain reason; the internal pipeline stays hidden.

## Which path should I use?

Factory-A is a **contract verifier, not a magic scanner**. It verifies declared
contracts and tests with the selected gate profile. **No spec means no full
certification.** A PASS covers the checks performed; it is not a zero-bug promise.

| Your starting point | Path | First action |
|---|---|---|
| I want to try Factory-A | **A — Included demo** | Add the Master Guide and verify the bundled safe_stats example |
| I already have Python code | **B — Lite Gate, then spec pack** | Run the fast check, then draft and review the expected behavior |
| I want to build new code | **C — Spec-pack template** | Adapt the bundled example contracts before building |

### A) Run the included demo

Install Python 3.10+ and run `python -m pip install pytest pyyaml`.
Open a scratch folder in VS Code, then run **Factory-A: Add Master Guide to Folder**
from the Command Palette. This adds the guide and `factory_a_examples/`.
Open `factory_a_examples/safe_stats` as the workspace folder in VS Code, then run
**Factory-A: Verify Folder (full gate)**. Expect Verified/PASS; inspect the report and
receipt output. Compare the example spec, `.factory-a/` contracts and golden tests.

### B) Check existing code, then generate a spec pack

Run **Factory-A: Check for Hallucinated Names (fast)** on your Python folder and
review the Problems panel. This is **Lite Gate**: the existing `--halonly` Python
phantom-name/syntax pre-check. It does not run tests, verify the full contract or
replay determinism, or issue a certification receipt. A Lite PASS only means no
offenders were reported; non-Python files are outside its coverage.

Add the Master Guide to a scratch folder to obtain the worked template, then ask
your AI:

> Read my existing code and FACTORY_A_START_HERE.md. Draft the five-file spec pack
> using factory_a_examples/safe_stats as the template. Do not change my code yet.
> Separate observed behavior from intended requirements. Mark uncertainties as
> QUESTIONS. Propose independently justified expected outputs and wait for my
> review before treating the draft as the contract.

Review inputs, outputs, edge cases and allowed errors. Resolve QUESTIONS, approve
the contract, then adapt the code and run **Verify Folder (full gate)**. AI-generated
specs are drafts; do not copy current implementation outputs blindly into tests.

### C) Build new code from a spec-pack template

Run **Factory-A: Add Master Guide to Folder** in your new workspace. Use
`factory_a_examples/safe_stats` as a template for `SMART_SPEC_<M>.md`,
`GOLDEN_IO_LOCK_<M>.yaml`, `<M>_REASON_CODES.yaml`, `INVARIANTS_<M>.yaml` and
`test_golden_<M>.py`. Keep the contract YAMLs under `.factory-a/` as shown in the
example, and update the test paths, names, requirements and expected values.

Review the spec and independently justified tests with the owner before building.
Ask your AI to follow the Master Guide, then run **Verify Folder (full gate)**.
Use the `general` profile for normal app code or `strict` for pure deterministic
logic. Inspect the report and receipt; spec changes require owner review.

For CLI users, run these from the standalone Factory-A repository root:

```bash
python run_gate.py examples/safe_stats --profile general
python run_gate.py "<your-module-folder>" --halonly
python run_gate.py "<your-module-folder>" --profile general
```

## New in v0.6 — MCP server bundled (any AI client)

The extension ships a bundled MCP server. Any AI client that speaks MCP — **Claude Code, Claude Desktop,
Cursor, Codex CLI, GitHub Copilot** — can call the Factory-A gate + memory map directly:

- **Command Palette → "Factory-A: Show MCP Server Setup"** — copies the absolute path to `server.py`
  and opens the setup README with per-client config snippets.

6 tools exposed via MCP (all execute real side effects, no prompt wrappers):
- `factory_a_run_gate` — deterministic gate on a module folder
- `memory_map_pack` / `memory_map_validate` / `memory_map_save` — append-only YAML knowledge nodes
- `worker_deepseek` / `worker_kimi` — delegate bulk writing to cheap workers (requires their API keys)

It drives the Python engine (`factory_a_pkg`) as a subprocess — your AI does the building; this is the in-editor surface + the gate + the MCP server.

## Requirements
- **Python** on PATH. For the full **Verify Folder** gate also: `pip install pytest pyyaml`
  (the gate runs your tests + reads its config). The fast **Check Hallucinated Names** needs only Python.

## Setup
- **Nothing to configure** — the FULL gate engine is bundled inside the extension (`engine/`), so BOTH
  commands work out of the box. (You can still override **Factory-A: Home** to point at your own engine.)
- Optional settings: **Python Path** + **Profile** (general/strict).

## Package and publish

From `vscode_extension/`, run:

```bash
npx @vscode/vsce package --no-dependencies
```

The package version is defined in `package.json`; do not rename an old VSIX to
pretend it is a new release. Test the generated VSIX locally, then upload it as
an update to publisher `i1980200888`, extension `factory-a`, in Marketplace.
The bundled engine and MCP server remain included.

## Inline diagnostics (DONE)
"Check for Hallucinated Names" now puts **red squiggles** under each phantom name and lists them in the
**Problems panel** (click → jump to the line) — the UI devs actually use, not a log to read. Pipeline:
`hallucination_gate` returns `(name, line, col)` → `run_gate.py --halonly --json` emits machine-readable
diagnostics → the extension maps them to `vscode.Diagnostic`. Validated: `node --check` OK, JSON contract
verified (clean → empty, phantom → file/line/col), no regression in the gate self-tests.

## Status (honest)
- **Done**: commands + output panel + notifications + settings + **inline diagnostics (squiggles/Problems)**.
- **Not yet**: live-tested inside a VS Code host (needs `vsce package` + install on a machine with VS Code),
  status-bar item, license gating, marketplace publishing. This is a lean installable surface for a market test.
