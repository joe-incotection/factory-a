#!/usr/bin/env python3
"""Factory-A MCP Server — verify AI-generated code with a deterministic
gate + persistent knowledge graph. Works with any MCP client (Claude
Desktop, Cursor, Claude Code, Codex CLI, ...).

Tools (6, all execute real side effects — no prompt wrappers):

  factory_a_run_gate    — subprocess run_gate.py; verdict + tail
  memory_map_pack       — read past knowledge nodes as context packet
  memory_map_validate   — schema check on the workspace's memory map
  memory_map_save       — append a new YAML node (append-only, auto-id)
  worker_deepseek       — delegate to DeepSeek (cheap worker)
  worker_kimi           — delegate to Kimi/Moonshot (long-context worker)

Register in your MCP client:

    {"mcpServers": {"factory-a": {
        "command": "python",
        "args": ["<absolute path>/factory_a_pkg/mcp_server/server.py"]
    }}}

Env vars (put in .env next to this file — see .env.example):
    DEEPSEEK_API_KEY    — required for worker_deepseek
    MOONSHOT_API_KEY    — required for worker_kimi
    FACTORY_A_HOME      — optional override for factory_a_pkg root
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── .env auto-loader (this dir only) ───────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent / ".env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(),
                              _v.strip().strip('"').strip("'"))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERR: mcp SDK not installed. Run: pip install mcp",
          file=sys.stderr)
    sys.exit(2)

mcp = FastMCP("factory-a")


# ─── Path SSOT ──────────────────────────────────────────────────────
def _paths() -> dict:
    """Single source of truth. FACTORY_A_HOME env overrides; otherwise
    infer from this file's parent-of-parent (this file lives in
    factory_a_pkg/mcp_server/, so ../..'s parent = factory_a_pkg)."""
    fa_home = os.environ.get("FACTORY_A_HOME")
    if fa_home:
        factory_a_home = Path(fa_home).resolve()
    else:
        factory_a_home = Path(__file__).resolve().parent.parent
    return {
        "factory_a_home": factory_a_home,
        "run_gate": factory_a_home / "run_gate.py",
    }


def _tail(text: str, n: int) -> tuple[str, bool]:
    """Return (last-N-lines-joined, was_truncated)."""
    lines = (text or "").splitlines()
    return "\n".join(lines[-n:]), len(lines) > n


def _run_subprocess(args, *, timeout: int, extra_env: dict = None):
    """Uniform subprocess.run — forces UTF-8 both directions to defeat
    Windows charmap encode errors from child prints (checkmarks, box
    chars, etc.)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        args, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


# ═════════════════════ Tool 1 — factory_a_run_gate ══════════════════

@mcp.tool()
def factory_a_run_gate(folder: str, profile: str = "general",
                        timeout: int = 600) -> dict:
    """Run the Factory-A deterministic gate on a module folder.
    Executes `python run_gate.py <folder> --profile <profile>`, which
    checks (in order): no hallucinated names → tests 100% →
    replay-deterministic → emits a receipt on PASS.

    Args:
        folder: absolute path to the module folder to certify
        profile: "general" (I/O allowed) or "strict" (pure logic)
        timeout: seconds before subprocess kill (default 600)

    Returns:
        {verdict: PASS|FAIL|ERROR, returncode, folder, profile,
         stdout_tail, stdout_truncated, stderr_tail, stderr_truncated}
    """
    p = _paths()
    if not p["run_gate"].exists():
        return {"verdict": "ERROR",
                "reason": f"run_gate.py not found at {p['run_gate']} "
                           "(set FACTORY_A_HOME env var)",
                "folder": folder, "profile": profile}
    if not Path(folder).is_dir():
        return {"verdict": "ERROR",
                "reason": f"folder not found: {folder}",
                "folder": folder, "profile": profile}
    try:
        proc = _run_subprocess(
            [sys.executable, str(p["run_gate"]), folder,
             "--profile", profile],
            timeout=timeout,
            extra_env={"FACTORY_A_HOME": str(p["factory_a_home"])},
        )
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR",
                "reason": f"gate timed out after {timeout}s",
                "folder": folder, "profile": profile}
    stdout_tail, stdout_trunc = _tail(proc.stdout, 25)
    stderr_tail, stderr_trunc = _tail(proc.stderr, 15)
    return {
        "verdict": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "folder": folder,
        "profile": profile,
        "stdout_tail": stdout_tail,
        "stdout_truncated": stdout_trunc,
        "stderr_tail": stderr_tail,
        "stderr_truncated": stderr_trunc,
    }


# ═════════════════════ Memory map — shared helpers ══════════════════

_MEMORY_DIR_NAME = ".factory-a/memory_map"
_NODE_TYPES = {"KNOWLEDGE_FACT", "FORMULA", "REASONING_PATTERN"}
_REQUIRED = ["node_id", "node_type", "title", "layer", "claim",
              "evidence"]
_EVIDENCE_REQ = ["source", "status"]


def _memory_dir(workspace: str) -> Path:
    return Path(workspace) / _MEMORY_DIR_NAME


def _load_all_nodes(bm_dir: Path):
    """Return list of (file_path, node_dict) across all *.yaml.
    Silently skips unparseable files."""
    try:
        import yaml
    except ImportError:
        return None, "PyYAML not installed (pip install pyyaml)"
    nodes = []
    if not bm_dir.is_dir():
        return nodes, None
    for f in sorted(bm_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for n in (data.get("candidates") or []):
            if isinstance(n, dict):
                nodes.append((f, n))
    return nodes, None


# ═════════════════════ Tool 2 — memory_map_pack ═════════════════════

@mcp.tool()
def memory_map_pack(workspace: str, keyword: str = "",
                     node_type: str = "", full: bool = False) -> dict:
    """Read <workspace>/.factory-a/memory_map/*.yaml — return past
    knowledge nodes (KNOWLEDGE_FACT / FORMULA / REASONING_PATTERN)
    as BOTH structured payload AND human-readable packet_text.

    Call this at the START of a session so you don't re-derive what
    prior sessions already learned.

    Args:
        workspace: absolute path to the workspace folder
        keyword: optional substring match on title/claim (case-insensitive)
        node_type: KNOWLEDGE_FACT | FORMULA | REASONING_PATTERN
        full: include claim body + evidence (default: titles only)

    Returns:
        {status, workspace, node_count, nodes: [...], packet_text: str}
    """
    bm_dir = _memory_dir(workspace)
    all_nodes, err = _load_all_nodes(bm_dir)
    if err:
        return {"status": "ERROR", "reason": err, "workspace": workspace}
    filtered = []
    for _f, n in all_nodes:
        if node_type and n.get("node_type") != node_type:
            continue
        if keyword:
            hay = (str(n.get("title") or "") + " "
                   + str(n.get("claim") or "")).lower()
            if keyword.lower() not in hay:
                continue
        filtered.append(n)
    # Render human-readable packet
    lines = [f"# memory_map packet — {len(filtered)} nodes\n"]
    for n in filtered:
        nid = n.get("node_id", "?")
        nt = n.get("node_type", "?")
        title = str(n.get("title") or "").strip()
        status = (n.get("evidence") or {}).get("status", "?")
        lines.append(f"- [{nid}] ({nt}, {status}) {title}")
        if full:
            claim = str(n.get("claim") or "").strip()
            if claim:
                for cl in claim.splitlines():
                    lines.append(f"    {cl}")
            ev = n.get("evidence") or {}
            if ev.get("source"):
                lines.append(f"    evidence.source: {ev['source']}")
            if ev.get("replay_artifact"):
                lines.append(
                    f"    evidence.replay_artifact: {ev['replay_artifact']}")
            links = n.get("linked_law_nodes") or []
            if links:
                lines.append(f"    linked: {', '.join(links)}")
            lines.append("")
    packet_text = "\n".join(lines) if filtered else "(no matching nodes)"
    return {
        "status": "OK",
        "workspace": workspace,
        "node_count": len(filtered),
        "nodes": filtered,
        "packet_text": packet_text,
    }


# ═════════════════════ Tool 3 — memory_map_validate ═════════════════

@mcp.tool()
def memory_map_validate(workspace: str) -> dict:
    """Schema check on <workspace>/.factory-a/memory_map/*.yaml.
    Call after saving a new node to catch missing evidence, duplicate
    node_ids, unknown node_type, or broken linked_law_nodes refs.

    Returns:
        {status: OK|HAS_ERRORS, errors: [...], warnings: [...],
         node_count, workspace}
    """
    bm_dir = _memory_dir(workspace)
    all_nodes, err = _load_all_nodes(bm_dir)
    if err:
        return {"status": "ERROR", "reason": err, "workspace": workspace}
    errors, warnings = [], []
    seen_ids = {}
    for f, n in all_nodes:
        nid = n.get("node_id") or "<no-id>"
        for k in _REQUIRED:
            if k not in n or n[k] in (None, ""):
                errors.append(
                    f"{f.name}:{nid} missing required field '{k}'")
        nt = n.get("node_type")
        if nt and nt not in _NODE_TYPES:
            warnings.append(
                f"{f.name}:{nid} unknown node_type '{nt}' "
                f"(expected {sorted(_NODE_TYPES)})")
        ev = n.get("evidence")
        if isinstance(ev, dict):
            for k in _EVIDENCE_REQ:
                if k not in ev or ev[k] in (None, ""):
                    errors.append(
                        f"{f.name}:{nid} evidence.{k} missing")
            if nt == "KNOWLEDGE_FACT" and not ev.get("replay_artifact"):
                warnings.append(
                    f"{f.name}:{nid} KNOWLEDGE_FACT without "
                    "evidence.replay_artifact")
        elif ev is not None:
            errors.append(f"{f.name}:{nid} evidence must be a dict")
        if n.get("node_id"):
            if nid in seen_ids:
                errors.append(
                    f"{f.name}:{nid} duplicate node_id "
                    f"(first seen in {seen_ids[nid]})")
            else:
                seen_ids[nid] = f.name
    # forward-ref check
    for f, n in all_nodes:
        nid = n.get("node_id", "<no-id>")
        for link in (n.get("linked_law_nodes") or []):
            if isinstance(link, str) and link and link not in seen_ids:
                warnings.append(
                    f"{f.name}:{nid} linked_law_nodes references "
                    f"unknown '{link}'")
    return {
        "status": "OK" if not errors else "HAS_ERRORS",
        "workspace": workspace,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(seen_ids),
    }


# ═════════════════════ Tool 4 — memory_map_save ═════════════════════

@mcp.tool()
def memory_map_save(workspace: str, node: dict,
                     topic_file: str = "") -> dict:
    """Append a new knowledge node to <workspace>/.factory-a/memory_map/.
    Enforces the APPEND-ONLY law: never edits an existing claim; new
    facts get a NEW node that supersedes and links back to the old.

    Auto-generates `node_id` if missing (based on node_type + slug +
    monotonic counter). Auto-selects/creates the topic file if not
    specified (based on domain hint in the node).

    Args:
        workspace: absolute path to the workspace folder
        node: the node dict (must have node_type + title + claim + evidence.source + evidence.status)
        topic_file: optional filename (without .yaml). If empty,
                    derived from node_type + first word of title.

    Returns:
        {status: OK|ERROR, node_id, file, workspace, total_nodes}

    NOTE: after save, ALWAYS call memory_map_validate to catch any
    schema drift the LLM introduced.
    """
    try:
        import yaml
    except ImportError:
        return {"status": "ERROR",
                "reason": "PyYAML not installed (pip install pyyaml)"}
    if not isinstance(node, dict):
        return {"status": "ERROR", "reason": "node must be a dict"}
    nt = node.get("node_type")
    if nt not in _NODE_TYPES:
        return {"status": "ERROR",
                "reason": f"node_type must be one of "
                          f"{sorted(_NODE_TYPES)}, got: {nt!r}"}
    title = str(node.get("title") or "").strip()
    if not title:
        return {"status": "ERROR", "reason": "node.title required"}
    if not (node.get("claim") or "").strip():
        return {"status": "ERROR", "reason": "node.claim required"}
    ev = node.get("evidence") or {}
    if not isinstance(ev, dict) or not ev.get("source") \
            or not ev.get("status"):
        return {"status": "ERROR",
                "reason": "node.evidence must include source + status"}

    bm_dir = _memory_dir(workspace)
    bm_dir.mkdir(parents=True, exist_ok=True)

    # existing nodes for duplicate check + counter
    all_nodes, _err = _load_all_nodes(bm_dir)
    existing_ids = {n.get("node_id") for _f, n in all_nodes
                     if n.get("node_id")}

    # Assign / validate node_id
    if node.get("node_id"):
        if node["node_id"] in existing_ids:
            return {"status": "ERROR",
                    "reason": f"node_id already exists: "
                              f"{node['node_id']} (append-only — pick "
                              "a new id or supersede via a new node)"}
    else:
        # Auto: <TYPE>__GEN__<slug>__<NNN>
        prefix = {"KNOWLEDGE_FACT": "FACT",
                   "FORMULA": "FORMULA",
                   "REASONING_PATTERN": "REASONING_PATTERN"}[nt]
        slug_source = title.lower()
        slug = "".join(c if c.isalnum() else "_" for c in slug_source)
        slug = "_".join(w for w in slug.split("_") if w)[:40] or "node"
        counter = 1
        for exist in existing_ids:
            if isinstance(exist, str) and exist.startswith(prefix):
                tail = exist.rsplit("__", 1)[-1]
                if tail.isdigit():
                    counter = max(counter, int(tail) + 1)
        node["node_id"] = f"{prefix}__GEN__{slug}__{counter:03d}"

    # Topic file
    if topic_file:
        target = bm_dir / f"{topic_file}.yaml"
    else:
        # derive from type + first word of title
        first_word = title.split()[0].lower() if title else "misc"
        first_word = "".join(c if c.isalnum() else "_" for c in first_word)
        target = bm_dir / f"{nt.lower()}_{first_word}.yaml"

    # Append (create-if-missing)
    if target.is_file():
        try:
            data = yaml.safe_load(target.read_text(encoding="utf-8"))
        except Exception as e:
            return {"status": "ERROR",
                    "reason": f"failed to parse existing "
                              f"{target.name}: {e}"}
        if not isinstance(data, dict):
            data = {"candidates": []}
        data.setdefault("candidates", [])
        data["candidates"].append(node)
    else:
        data = {"candidates": [node]}

    try:
        yaml_text = yaml.safe_dump(data, sort_keys=False,
                                    allow_unicode=True, width=100)
        target.write_text(yaml_text, encoding="utf-8")
    except Exception as e:
        return {"status": "ERROR",
                "reason": f"failed to write {target}: {e}"}

    return {
        "status": "OK",
        "node_id": node["node_id"],
        "file": str(target),
        "workspace": workspace,
        "total_nodes": len(existing_ids) + 1,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


# ═════════════════════ Worker HTTP (shared) ═════════════════════════

_RETRYABLE = {429, 500, 502, 503, 504}


def _openai_compat(*, base_url, api_key, model, prompt, system, timeout,
                     json_mode, temperature, max_tokens=None,
                     max_retries=3) -> dict:
    """Shared OpenAI-compat chat call. Retries on 429/5xx/timeout
    only (permanent 400/401/403 fail immediately). json_mode=True
    auto-parses response and fails loud on parse error."""
    if not api_key:
        return {"error": "API_KEY_MISSING", "content": None, "model": model}
    try:
        import urllib.request
        import urllib.error
    except Exception as e:
        return {"error": "URLLIB_IMPORT_FAIL", "content": None,
                "detail": str(e), "model": model}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body_dict = {"model": model, "messages": messages,
                 "temperature": temperature, "stream": False}
    if json_mode:
        body_dict["response_format"] = {"type": "json_object"}
    if max_tokens is not None:
        body_dict["max_tokens"] = max_tokens
    body = json.dumps(body_dict).encode("utf-8")

    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            if e.code in _RETRYABLE and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                last_err = {"error": f"HTTP_{e.code}", "content": None,
                            "detail": body_text, "model": model,
                            "attempts": attempt + 1}
                continue
            return {"error": f"HTTP_{e.code}", "content": None,
                    "detail": body_text, "model": model,
                    "attempts": attempt + 1}
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                last_err = {"error": "TIMEOUT_OR_NETWORK",
                            "content": None, "detail": str(e),
                            "model": model, "attempts": attempt + 1}
                continue
            return {"error": "TIMEOUT_OR_NETWORK", "content": None,
                    "detail": str(e), "model": model,
                    "attempts": attempt + 1}
        except Exception as e:
            return {"error": type(e).__name__, "content": None,
                    "detail": str(e), "model": model}
    else:
        return last_err or {"error": "RETRIES_EXHAUSTED",
                              "content": None, "model": model}

    try:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
    except Exception:
        return {"error": "UNEXPECTED_RESPONSE_SHAPE", "content": None,
                "raw": str(data)[:500], "model": model}
    result = {"error": None, "content": content, "usage": usage,
              "model": data.get("model", model)}
    if json_mode:
        try:
            result["parsed"] = json.loads(content)
        except Exception as e:
            result["error"] = "JSON_MODE_PARSE_FAIL"
            result["parse_detail"] = str(e)
    return result


# ═════════════════════ Tool 5 — worker_deepseek ═════════════════════

@mcp.tool()
def worker_deepseek(prompt: str, system: str = "",
                     model: str = "deepseek-chat",
                     json_mode: bool = False,
                     timeout: int = 120) -> dict:
    """Delegate work to DeepSeek (cheap worker) to save Opus/Claude tokens.
    Best for: bulk code writing, boilerplate, large-context summarize.

    Requires DEEPSEEK_API_KEY in env (or .env next to server.py).
    """
    return _openai_compat(
        base_url="https://api.deepseek.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=model, prompt=prompt, system=system,
        timeout=timeout, json_mode=json_mode, temperature=0.2,
    )


# ═════════════════════ Tool 6 — worker_kimi ═════════════════════════

@mcp.tool()
def worker_kimi(prompt: str, system: str = "",
                 model: str = "kimi-k2.7-code",
                 json_mode: bool = False,
                 timeout: int = 120,
                 max_tokens: int = 8000) -> dict:
    """Delegate work to Kimi (Moonshot). Best for: bulk code writing,
    long-context read. Uses temperature=1 (Kimi requirement).
    max_tokens=8000 default — reasoning models can burn budget on
    hidden thinking and leave content empty without an explicit cap.

    Requires MOONSHOT_API_KEY in env (or .env next to server.py).
    """
    return _openai_compat(
        base_url="https://api.moonshot.ai/v1",
        api_key=os.environ.get("MOONSHOT_API_KEY", ""),
        model=model, prompt=prompt, system=system,
        timeout=timeout, json_mode=json_mode, temperature=1.0,
        max_tokens=max_tokens,
    )


# ═════════════════════ Entry ══════════════════════════════════════════

if __name__ == "__main__":
    mcp.run(transport="stdio")
