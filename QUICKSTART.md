# Factory-A · Quickstart (5 minutes to your first Verified ✓)

Prove Factory-A works end-to-end on a tiny module before you install anything else.

## Which path should I use?

- **A — Try the demo:** follow the commands below.
- **B — Existing code without a spec pack:** start with
  `python run_gate.py "<your-module-folder>" --halonly` (Python pre-check only),
  then draft and owner-review a spec pack before full verification.
- **C — New code:** adapt the five-file template in `examples/safe_stats/`,
  review the contract, then build and run the full gate.

Factory-A is a contract verifier, not a magic scanner: **no spec means no full
certification**. See [the complete onboarding flow](README.md#which-path-should-i-use).

## Prereq
- Python 3.10+ on PATH
- `pip install pytest pyyaml`

## Run the bundled example (no install needed)

```
git clone https://github.com/joe-incotection/factory-a
cd factory-a
python run_gate.py examples/safe_stats --profile general
```

Expected tail (last 3 lines):
```
[receipt] Decision_Receipt written -> examples/safe_stats/receipts/Decision_Receipt_<id>.json
=== VERDICT: PASS (report: examples/_safe_stats_gate_report.json) ===
```

That was: `safe_stats` module went through the deterministic gate (no hallucinated names → tests 100% → replay-deterministic) and a signed receipt was written. Open the receipt JSON — that's the proof this run produced.

## Register the MCP server with your AI client (2 minutes)

Pick your client:

```
python install.py cursor --write             # merges into ~/.cursor/mcp.json (with .bak)
python install.py claude-desktop-win --write # or -mac
python install.py claude-code --write
python install.py codex                      # prints TOML — paste manually
```

Restart the client → 6 tools appear:
- `factory_a_run_gate`
- `memory_map_pack` / `memory_map_validate` / `memory_map_save`
- `worker_deepseek` / `worker_kimi` (need API keys in `mcp_server/.env`)

## Try it on your own project

```
# In your project folder, drop the Master Guide
cp path/to/factory-a/FACTORY_A_START_HERE.md .

# Then in your AI (any client): paste this
```
> Read `FACTORY_A_START_HERE.md` and act as my Factory-A Master.

Choose Path B for existing code or C for new code. Your AI drafts the spec pack and golden tests; you review the expected behavior before it adapts or builds the module. When it calls `factory_a_run_gate`, you see **PASS** + a receipt, or **FAIL** + the reason it iterates on.

## Multi-module projects (v0.7+)

Add `depends_on:` in `project_manifest.yaml` and the wiring gates run automatically:

```yaml
modules:
  - name: parser
  - name: analyzer
    depends_on: [parser]
  - name: reporter
    depends_on: [analyzer]
```

Now if `analyzer` expects a field `parser` doesn't provide, or imports a function `parser` doesn't export, Factory-A blocks the build before it ships.

## Get feedback / report issues

- **Issues**: https://github.com/joe-incotection/factory-a/issues
- **Discussions**: https://github.com/joe-incotection/factory-a/discussions
- **Website**: https://lxrautomation.com
