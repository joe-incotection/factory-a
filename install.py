#!/usr/bin/env python3
"""Factory-A install helper — writes the MCP server config snippet for
your chosen AI client. Non-destructive: prints the exact JSON/TOML to
add and (with --write) merges it into the client's config file after
a backup.

Usage:

    python install.py                              # list clients + show snippet
    python install.py claude-desktop               # show config path + snippet for one
    python install.py cursor --write               # merge into ~/.cursor/mcp.json (backup .bak)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "mcp_server" / "server.py"
_server_str = str(SERVER).replace("\\", "/")

CLIENTS = {
    "claude-code": {
        "config": Path.home() / ".claude" / "mcp_settings.json",
        "format": "json",
    },
    "claude-desktop-win": {
        "config": Path(os.environ.get("APPDATA", "~/AppData/Roaming"))
                  / "Claude" / "claude_desktop_config.json",
        "format": "json",
    },
    "claude-desktop-mac": {
        "config": Path.home() / "Library" / "Application Support"
                  / "Claude" / "claude_desktop_config.json",
        "format": "json",
    },
    "cursor": {
        "config": Path.home() / ".cursor" / "mcp.json",
        "format": "json",
    },
    "codex": {
        "config": Path.home() / ".codex" / "config.toml",
        "format": "toml",
    },
}


def _json_snippet() -> str:
    return json.dumps({
        "mcpServers": {
            "factory-a": {
                "command": "python",
                "args": [_server_str],
            }
        }
    }, indent=2)


def _toml_snippet() -> str:
    return (
        "[mcp_servers.factory-a]\n"
        f'command = "python"\n'
        f'args = ["{_server_str}"]\n'
    )


def show(name: str) -> None:
    info = CLIENTS[name]
    fmt = info["format"]
    print(f"\n=== {name} ===")
    print(f"config path: {info['config']}")
    print(f"format     : {fmt}")
    print(f"snippet    :\n")
    print(_json_snippet() if fmt == "json" else _toml_snippet())


def write(name: str) -> int:
    info = CLIENTS[name]
    cfg = info["config"]
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if info["format"] != "json":
        print(f"--write is JSON-only for now. TOML clients: paste the "
              f"snippet into {cfg} manually.", file=sys.stderr)
        return 1
    existing = {}
    if cfg.is_file():
        try:
            existing = json.loads(cfg.read_text(encoding="utf-8") or "{}")
        except Exception as e:
            print(f"could not parse existing {cfg}: {e}", file=sys.stderr)
            return 2
        # backup
        bak = cfg.with_suffix(cfg.suffix + ".bak")
        shutil.copy2(cfg, bak)
        print(f"backed up existing config -> {bak}")
    existing.setdefault("mcpServers", {})
    existing["mcpServers"]["factory-a"] = {
        "command": "python",
        "args": [_server_str],
    }
    cfg.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"wrote factory-a MCP entry -> {cfg}")
    print("restart your client, then the 6 factory-a tools will appear.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Factory-A MCP install helper")
    ap.add_argument("client", nargs="?", choices=CLIENTS.keys(),
                    help="client name; omit to list all")
    ap.add_argument("--write", action="store_true",
                    help="merge into the client's config (JSON only)")
    args = ap.parse_args()
    if not SERVER.exists():
        print(f"ERR: mcp_server/server.py not found at {SERVER}",
              file=sys.stderr)
        return 2
    if args.client is None:
        print("Factory-A MCP server:")
        print(f"  {SERVER}\n")
        print("Supported clients (pass one as an arg for its snippet):")
        for k in CLIENTS:
            print(f"  - {k}   ({CLIENTS[k]['config']})")
        print("\nExamples:")
        print("  python install.py claude-desktop-win")
        print("  python install.py cursor --write")
        return 0
    if args.write:
        return write(args.client)
    show(args.client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
