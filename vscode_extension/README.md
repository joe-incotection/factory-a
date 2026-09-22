# Factory-A — VS Code Extension (shell / MVP)

**AI coding that doesn't fall apart at scale.** Every change is *verified, not trusted*: it must
pass a deterministic gate (no hallucinated names → tests 100% → replay-deterministic) before it
ships. You see **Verified ✓ / Blocked ✗** + a plain reason; the internal pipeline stays hidden.

## How to use (spec-first)
Factory-A is a **spec-first production line**, not a linter on arbitrary code. The flow:
1. **Command Palette → "Factory-A: Add Master Guide to Folder"** — drops `FACTORY_A_START_HERE.md` + a
   worked example into your folder and copies a one-line instruction to your clipboard.
2. **Paste it to your AI** (Cursor/Copilot/Claude): *"Read FACTORY_A_START_HERE.md and act as my Master."*
   Your AI writes the spec (Golden I/O + golden tests) and builds the code.
3. **Command Palette → "Factory-A: Verify Folder (full gate)"** — gates the module you built →
   `✓ Verified` or `✗ Blocked` + reason. (The gate needs a Factory-A spec; on a folder without one it
   tells you to start with the Master Guide.)

Plus a standalone helper that works on any Python file:
- **"Check for Hallucinated Names (fast)"** — 0-token static check: red squiggles under any name used but
  never defined/imported (invented variable / typo'd module / phantom API).

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

## Build → .vsix → upload (publish)
```bash
cd vscode_extension
npm install -g @vscode/vsce      # one-time
vsce package                     # -> Incotection.factory-a-0.1.0.vsix
```
Then on the Marketplace publisher page → **New extension → Visual Studio Code → upload the .vsix**.
(Optional local test first: open this folder in VS Code → press **F5** to launch an Extension Host.)
`vsce` may warn about a missing icon/repository/LICENSE — those are warnings, it still packages; add an
icon later for a nicer listing. The packaged `.vsix` contains only the extension + the minimal gate
engine — **no prompts/, no ODE, no internal jargon** (IP stays out, per `_STEALTH_IP_REGISTER.md`).

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
