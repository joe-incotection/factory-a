# Factory-A

**Let any AI ship code that actually works — deterministic gate + append-only memory.**

Every change is *verified, not trusted*: it must pass a hard-coded gate (no hallucinated names → tests 100% → replay-deterministic) before it ships, with a tamper-evident receipt. What one AI session learns is saved as an append-only YAML knowledge graph — every future session (any vendor) reads it back. Your project's memory is portable, git-friendly, cross-vendor.

- **Website:** https://lxrautomation.com
- **VS Code Marketplace:** [Factory-A — Verified AI Coding](https://marketplace.visualstudio.com/items?itemName=i1980200888.factory-a)
- **License:** MIT

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
3. Your AI writes a Golden-I/O spec + golden tests, then builds the code.
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
