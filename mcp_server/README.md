# Factory-A MCP Server

Verify AI-generated code with a **deterministic** gate + **append-only knowledge graph**. Works with any MCP client — Claude Code, Claude Desktop, Cursor, Codex CLI, VS Code Copilot.

## Why

- **Anti-hallucination** — every module the AI writes passes a hard-coded gate (no hallucinated names → tests 100% → replay-deterministic) before it ships. The verifier is subprocess Python, not another LLM.
- **Portable memory** — YAML nodes with `evidence.replay_artifact` + append-only law. Session A saves; Session B (or a different vendor) reads. Codex has run this pattern in a single session for 4+ months without drift.
- **Cost saver** — worker tools delegate bulk writing to DeepSeek / Kimi so your Opus/Claude context isn't burned on boilerplate.

## Setup (any MCP client)

```
pip install mcp pyyaml
```

Copy `.env.example` → `.env` in this folder, fill in `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` (only the ones you use). The server reads **only** the `.env` next to `server.py` — if you prefer a central `.env`, set process env vars before launching (setdefault means real env vars win).

Register with your MCP client — pick your client:

**Claude Code** (`~/.claude/mcp_settings.json`):
```json
{
  "mcpServers": {
    "factory-a": {
      "command": "python",
      "args": ["<ABSOLUTE PATH>/factory_a_pkg/mcp_server/server.py"]
    }
  }
}
```

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on Mac): same shape.

**Cursor** (`~/.cursor/mcp.json`, or workspace `.cursor/mcp.json`): same shape.

**Codex CLI** (`~/.codex/config.toml`):
```toml
[mcp_servers.factory-a]
command = "python"
args = ["<ABSOLUTE PATH>/factory_a_pkg/mcp_server/server.py"]
```

Restart the client → the 6 tools appear.

## Tools (6, all execute — no prompt wrappers)

### Verify

- `factory_a_run_gate(folder, profile="general", timeout=600)` — subprocess `run_gate.py`. Returns `{verdict: PASS|FAIL|ERROR, returncode, folder, profile, stdout_tail, stdout_truncated, stderr_tail, stderr_truncated}`.

### Memory map (Brain Map — YAML nodes, append-only)

- `memory_map_pack(workspace, keyword, node_type, full)` — read `<workspace>/.factory-a/memory_map/*.yaml`. Returns `{status, workspace, node_count, nodes: [...], packet_text}`. Machine gets structured; humans get rendered — pick per use.

- `memory_map_validate(workspace)` — schema check. Returns `{status, errors, warnings, node_count, workspace}`.

- `memory_map_save(workspace, node, topic_file="")` — append a new node. **Enforces append-only law** (duplicate `node_id` → ERROR). Auto-assigns `node_id` if omitted (`<TYPE>__GEN__<slug>__<NNN>`). Auto-picks topic file if omitted. Requires: `node_type` (KNOWLEDGE_FACT / FORMULA / REASONING_PATTERN) + `title` + `claim` + `evidence.source` + `evidence.status`.

### Workers (cost saver)

- `worker_deepseek(prompt, system, model, json_mode, timeout)` — HTTP with retries on 429/5xx/timeout, `json_mode=True` forces `response_format: json_object` and auto-parses.
- `worker_kimi(prompt, system, model, json_mode, timeout, max_tokens=8000)` — same shape. Temperature=1 (Kimi requirement). `max_tokens=8000` default so reasoning models don't burn budget on hidden thinking and leave content empty.

## Design notes

- **Server is stateless.** All state lives in the workspace (`<ws>/.factory-a/memory_map/`, module folders, receipts). Restart is harmless.
- **Path SSOT** — `_paths()` helper. `FACTORY_A_HOME` env overrides; otherwise inferred from `server.py`'s parent-of-parent.
- **Append-only law** — `memory_map_save` refuses duplicate `node_id`. If a fact changes, save a NEW node that supersedes the old and reference the old in `linked_law_nodes`.
- **UTF-8 uniform** — subprocess helper forces `PYTHONIOENCODING=utf-8` + decode `errors="replace"`; no Windows charmap surprises when child prints emoji/box chars.

## Deliberately NOT here

- No "planner" tools that return instruction strings. Your Master AI plans in-chat; every tool here executes a real side effect.
- No auth / billing / dashboard — this is a single-file MCP server, not a SaaS.
- No cross-vendor abstraction — Master AI decides which worker to call.

## Files

```
mcp_server/
├── server.py         # 6 tools (all executors)
├── .env              # your API keys (gitignored)
├── .env.example      # template
└── README.md
```
