# Factory-A

**Let any AI ship code that actually works — deterministic gate + append-only memory.**

Every change is *verified, not trusted*: it must pass a hard-coded gate (no hallucinated names → tests 100% → replay-deterministic) before it ships, with a tamper-evident receipt. What one AI session learns is saved as an append-only YAML knowledge graph — every future session (any vendor) reads it back. Your project's memory is portable, git-friendly, cross-vendor.

- **Website:** https://lxrautomation.com
- **VS Code Marketplace:** [Factory-A — Verified AI Coding](https://marketplace.visualstudio.com/items?itemName=i1980200888.factory-a)
- **License:** MIT

---

## Which path should I use?

Factory-A is a **contract verifier, not a magic scanner**. It checks code against
declared contracts, tests and the selected gate profile. **No spec means no full
certification.** A PASS is evidence for the checks performed, not a promise of
zero bugs or proof that the business requirements are correct.

| Your starting point | Choose | What you get |
|---|---|---|
| I want to understand Factory-A first | **A — Run the included demo** | A complete example of specs, code, tests and gate evidence |
| I already have code but no Factory-A spec pack | **B — Lite Gate, then draft a spec pack** | A limited pre-check, then an owner-reviewed contract for full verification |
| I want to build a new module | **C — Start from a spec-pack template** | Requirements and expected outputs agreed before implementation |

Run the commands below from the Factory-A repository root. The CLI works without
MCP setup; MCP lets your AI client call the same gate.

### A) Run the included demo

Prerequisite: Python 3.10+ on PATH.

```bash
python -m pip install pytest pyyaml
python run_gate.py examples/safe_stats --profile general
```

Expect a final PASS and a report at `examples/_safe_stats_gate_report.json`.
Check the receipt message and inspect the generated JSON under
`examples/safe_stats/receipts/`. Read the example's spec pack alongside its code
and golden tests to see what the result verifies. See [QUICKSTART.md](QUICKSTART.md).

### B) Check existing code, then generate a spec pack

**Lite Gate** here means the existing `--halonly` pre-check; there is no separate
`--lite` flag. Point it at your Python module folder:

```bash
python run_gate.py "<your-module-folder>" --halonly
python run_gate.py "<your-module-folder>" --halonly --json
```

This scans Python files for phantom names and syntax diagnostics. It does not run
tests, check the full contract, verify replay determinism or emit a certification
receipt. A Lite PASS only means the scanner found no reported offenders; check
JSON status for SKIP. Non-Python code is outside this pre-check's coverage.

Then give your AI this request:

> Read my existing code and `FACTORY_A_START_HERE.md`. Draft a Factory-A spec pack
> using `examples/safe_stats/` as the template. Do not modify my code yet. Separate
> observed behavior from intended requirements; mark uncertain behavior as
> QUESTIONS. Propose SMART_SPEC, GOLDEN_IO_LOCK, REASON_CODES, INVARIANTS and golden
> tests. Do not assume the current implementation is correct. Wait for my review
> of the expected behavior before treating the draft as the contract.

The owner reviews inputs, expected outputs, edge cases and error codes. Resolve
QUESTIONS and approve the contract, then adapt the code and run the full gate:

```bash
python run_gate.py "<your-module-folder>" --profile general
```

Tests need independently justified expected results, not values copied blindly
from the implementation. AI-generated specs are drafts, not automatic certification.

### C) Build new code the Factory-A way

Use the five files in [examples/safe_stats/](examples/safe_stats/) as a worked
spec-pack template, guided by [prompts/SPEC_AUTHOR_PROMPT.md](prompts/SPEC_AUTHOR_PROMPT.md).
Create them in your new module folder, rename SAFE_STATS identifiers for your
module and replace the example requirements and expected values.

1. Define purpose, public entry point, exact I/O and edge cases in `SMART_SPEC_<M>.md`.
2. Define schema in `GOLDEN_IO_LOCK_<M>.yaml`, allowed errors in `<M>_REASON_CODES.yaml`
   and testable laws in `INVARIANTS_<M>.yaml`.
3. Write `test_golden_<M>.py` with independently justified outputs, including
   asymmetric/oracle cases for numeric behavior. Have the owner review the contract.
4. Build through AIEL-0 → 3 using [FACTORY_A_START_HERE.md](FACTORY_A_START_HERE.md),
   then run the gate:

```bash
python run_gate.py "<new-module-folder>" --profile general
# For pure deterministic logic:
python run_gate.py "<new-module-folder>" --profile strict
```

Read failures, fix the responsible stage, and rerun. On PASS, inspect the report
and receipt and describe exactly what was verified. Spec changes require owner
review; do not weaken the contract merely to make failing code pass.

---

## Two ways to install

### A) VS Code / Cursor — one click

Install from marketplace, or `code --install-extension` on the released `.vsix`:

```
code --install-extension factory-a-0.6.2.vsix
```

Then Command Palette → **Factory-A: Show MCP Server Setup** — it copies the bundled MCP server path and opens the setup guide.

### B) Any other AI client (Claude Code, Claude Desktop, Cursor, Codex CLI, ...) — MCP server

```
git clone https://github.com/joe-incotection/factory-a
cd factory-a
pip install mcp pyyaml
python install.py            # writes the MCP config snippet for your client
```

Or manual — register in your client's `mcpServers`:

```json
{
  "mcpServers": {
    "factory-a": {
      "command": "python",
      "args": ["<absolute path>/mcp_server/server.py"]
    }
  }
}
```

Config paths per client:

| Client | Config file |
|---|---|
| Claude Code | `~/.claude/mcp_settings.json` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` (Windows) · `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) |
| Cursor | `~/.cursor/mcp.json` |
| Codex CLI | `~/.codex/config.toml` (TOML syntax — see `mcp_server/README.md`) |

Restart the client → 6 tools appear.

---

## The 6 MCP tools (all execute — no prompt wrappers)

| Tool | What it does |
|---|---|
| `factory_a_run_gate(folder, profile)` | Deterministic gate: hallucinated-names → tests 100% → replay-deterministic. PASS emits a receipt. |
| `memory_map_pack(workspace, keyword, node_type, full)` | Read past knowledge nodes as `{nodes, packet_text}`. |
| `memory_map_validate(workspace)` | Schema check on the workspace's memory map. |
| `memory_map_save(workspace, node)` | Append-only save. Duplicate `node_id` → ERROR. |
| `worker_deepseek(prompt, system, json_mode)` | Delegate bulk writing to DeepSeek (cheap). |
| `worker_kimi(prompt, system, json_mode, max_tokens=8000)` | Long-context worker. |

Requirements for the workers: put `DEEPSEEK_API_KEY` and/or `MOONSHOT_API_KEY` in `mcp_server/.env` (see `mcp_server/.env.example`).

---

## Quick start (any AI)

1. Open your project folder in your AI client.
2. Ask your AI: *"Read `FACTORY_A_START_HERE.md` and act as my Factory-A Master."*
3. Choose Path A, B or C above. For B/C, review the proposed spec pack and golden tests before the AI builds or adapts code.
4. Your AI calls `factory_a_run_gate` on the folder. PASS → done + receipt. FAIL → reason → iterate.
5. When you learn something worth keeping, your AI calls `memory_map_save` — the next session (any vendor) reads it back with `memory_map_pack`.

---

## Repo layout

```
factory-a/
├── README.md                       # you are here
├── LICENSE                         # MIT
├── FACTORY_A_START_HERE.md         # what you point your AI at
├── run_gate.py                     # the deterministic gate (CLI entry)
├── mcp_server/                     # standalone MCP server (6 tools)
├── vscode_extension/               # VS Code extension source + .vsix
├── examples/                       # worked spec packs (safe_stats, trinity_m1)
├── profiles/                       # verification profiles (general, strict)
├── stage_tests/                    # the gate stages (M8 / Stage2 / M7)
├── factory_core/                   # engine internals
├── prompts/                        # master prompt + spec-author prompt
└── install.py                      # one-shot MCP config helper
```

---

## Multi-module wiring (Gates I.5 + I.6, v0.7+)

For projects with more than one module, opt into wiring gates by declaring `depends_on:` in `project_manifest.yaml`:

```yaml
modules:
  - name: parser
  - name: analyzer
    depends_on: [parser]
  - name: reporter
    depends_on: [analyzer]
```

Factory-A then enforces, before the project ships:

- **I.5 — Shape match** — if B `depends_on` A, then B's `input_contract.required` fields must all appear in A's `output_contract.required`. Catches the silent bug where A renames a field and B still expects the old name.
- **I.6 — Import existence** — AST scan of B's source verifies every `from A import X` names something A actually exports. Catches hallucinated cross-module imports.
- **Topological build order** — derived from `depends_on`; cycles and missing deps are hard errors.

Legacy manifests (plain list of strings) skip these gates and keep working — opt in per project.

## Discipline (why this works)

1. **RECON before opinion** — read the digest / spec / test output first.
2. **"I don't know" is a complete answer** — insufficient evidence is a legitimate verdict.
3. **Evidence before claims** — separate what you verified from what you assumed.
4. **Test, not believe** — compile-clean ≠ behavior-correct.
5. **Small reversible steps** — one block / one screen at a time.
6. **Append-only memory** — never rewrite an old claim; add a new node that supersedes it.

These aren't Factory-A etiquette; they're how any AI coding at scale stays honest.
