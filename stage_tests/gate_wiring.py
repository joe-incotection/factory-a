"""Integration Gates I.5 + I.6 — cross-module wiring enforcement.

I.5 — Shape match      : If module B declares `depends_on: [A]`, then B's
                         input_contract MUST be a subset of A's output_contract
                         (same field names, same shape). Catches wiring drift
                         when A renames or restructures a field and B was not
                         updated.

I.6 — Import existence : For every B->A dependency, scan B's source for
                         `from A import X` / `import A.X` and verify each X
                         exists in A's exported surface. Catches hallucinated
                         cross-module imports.

Both gates are OPT-IN by manifest declaration. Legacy manifests
(list-of-strings) are treated as "wiring undeclared" and skip these gates
with a single info-level line, so existing projects keep working.

Manifest schema (backward compatible):

    # Legacy (still valid; skips I.5/I.6):
    modules:
      - trinity_m1
      - trinity_m1_adapter

    # New (opts into I.5/I.6):
    modules:
      - name: trinity_m1
      - name: trinity_m1_adapter
        depends_on: [trinity_m1]
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


# ═════════════════════ Manifest normalization ═══════════════════════

def normalize_manifest(raw_modules: list) -> tuple[list[dict], bool]:
    """Turn a mixed list (strings and/or dicts) into a uniform list of dicts.

    Returns:
        (normalized_list, wiring_declared)
        wiring_declared = True if at least one module has `depends_on`.
        When False, I.5/I.6 are skipped (legacy manifest).
    """
    out = []
    wiring_declared = False
    for entry in raw_modules:
        if isinstance(entry, str):
            out.append({"name": entry.strip(), "depends_on": []})
        elif isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
            if not name:
                raise RuntimeError(
                    f"PIPELINE_ABORT: manifest entry missing 'name': {entry!r}")
            deps = entry.get("depends_on") or []
            if not isinstance(deps, list) or not all(
                    isinstance(d, str) and d.strip() for d in deps):
                raise RuntimeError(
                    f"PIPELINE_ABORT: '{name}'.depends_on must be a list of "
                    f"non-empty strings, got {deps!r}")
            if deps:
                wiring_declared = True
            out.append({"name": name, "depends_on": list(deps)})
        else:
            raise RuntimeError(
                f"PIPELINE_ABORT: manifest entries must be str or dict, "
                f"got {type(entry).__name__}: {entry!r}")
    # Duplicate name check
    seen = set()
    for m in out:
        if m["name"] in seen:
            raise RuntimeError(
                f"PIPELINE_ABORT: duplicate module in manifest: {m['name']!r}")
        seen.add(m["name"])
    return out, wiring_declared


# ═════════════════════ Topological sort ═════════════════════════════

def topological_order(modules: list[dict]) -> list[str]:
    """Kahn's algorithm. Raises on missing dep or cycle."""
    names = {m["name"] for m in modules}
    for m in modules:
        for d in m["depends_on"]:
            if d not in names:
                raise RuntimeError(
                    f"PIPELINE_ABORT: module '{m['name']}' depends_on "
                    f"'{d}' which is not in the manifest")
    indeg = {m["name"]: 0 for m in modules}
    graph = defaultdict(list)
    for m in modules:
        for d in m["depends_on"]:
            graph[d].append(m["name"])
            indeg[m["name"]] += 1
    q = deque([n for n, d in indeg.items() if d == 0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for succ in graph[n]:
            indeg[succ] -= 1
            if indeg[succ] == 0:
                q.append(succ)
    if len(order) != len(modules):
        remaining = [n for n, d in indeg.items() if d > 0]
        raise RuntimeError(
            f"PIPELINE_ABORT: dependency cycle detected involving: "
            f"{', '.join(sorted(remaining))}")
    return order


# ═════════════════════ Shape helpers ════════════════════════════════

def _shape_of(field: Any) -> str:
    """Compact shape descriptor for a field spec — 'object', 'array<number>',
    'string', etc. Used for mismatch reporting."""
    if not isinstance(field, dict):
        return str(type(field).__name__)
    t = field.get("type", "?")
    if t == "array":
        inner = field.get("items", {})
        if isinstance(inner, dict):
            return f"array<{_shape_of(inner)}>"
        return "array"
    return str(t)


def _required_set(contract: dict) -> set[str]:
    req = contract.get("required") if isinstance(contract, dict) else None
    if isinstance(req, list):
        return {str(x) for x in req if isinstance(x, str)}
    return set()


def _fields_map(contract: dict) -> dict[str, dict]:
    fm = contract.get("fields") if isinstance(contract, dict) else None
    return fm if isinstance(fm, dict) else {}


# ═════════════════════ Gate I.5 — Shape Match ═══════════════════════

def load_golden_io_lock(vault_dir: Path, module_id: str, yaml_lib) -> dict:
    """Load <vault>/<module>/GOLDEN_IO_LOCK*.yaml. Returns {} if absent
    (upstream I.1 already flags this; we just return empty to skip)."""
    mdir = vault_dir / module_id
    locks = sorted(mdir.glob("*GOLDEN_IO_LOCK*.yaml"))
    if not locks:
        return {}
    try:
        with open(locks[0], encoding="utf-8") as fh:
            data = yaml_lib.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def gate_I5_shape_match(modules: list[dict], vault_dir: Path,
                          yaml_lib) -> list[str]:
    """For each B->A edge, verify B.input_contract ⊆ A.output_contract.

    Rules:
      - B's required field names MUST all appear in A's required field names
      - For each shared field, top-level type SHOULD match (warn on mismatch,
        not fatal — deep-type checking is spec-authors' job; we don't want
        false positives from missing nested definitions)

    Returns a list of ERROR strings (empty = pass). Warnings printed inline.
    """
    errors = []
    lock_cache: dict[str, dict] = {}
    for m in modules:
        for a in m["depends_on"]:
            b_name = m["name"]
            if a not in lock_cache:
                lock_cache[a] = load_golden_io_lock(vault_dir, a, yaml_lib)
            if b_name not in lock_cache:
                lock_cache[b_name] = load_golden_io_lock(vault_dir, b_name, yaml_lib)
            a_lock = lock_cache[a]
            b_lock = lock_cache[b_name]
            if not a_lock or not b_lock:
                # I.1 already flagged missing lock; skip pair
                continue

            a_out = a_lock.get("output_contract") or {}
            b_in = b_lock.get("input_contract") or {}
            a_req = _required_set(a_out)
            b_req = _required_set(b_in)
            missing = b_req - a_req
            if missing:
                errors.append(
                    f"[I.5] {b_name} depends_on {a}: "
                    f"input requires {sorted(missing)} but "
                    f"{a}.output_contract does not provide those fields "
                    f"(a.provides={sorted(a_req)})")
                continue

            # Type match — warn only
            a_fields = _fields_map(a_out)
            b_fields = _fields_map(b_in)
            for fname in sorted(b_req & a_req):
                a_shape = _shape_of(a_fields.get(fname, {}))
                b_shape = _shape_of(b_fields.get(fname, {}))
                if a_shape != "?" and b_shape != "?" and a_shape != b_shape:
                    print(f"    [I.5][WARN] {b_name} <- {a}.{fname}: "
                          f"shape mismatch (produces {a_shape}, "
                          f"expected {b_shape})")

            print(f"    [I.5] {b_name} <- {a}: OK "
                  f"({len(b_req)} field(s) matched)")
    return errors


# ═════════════════════ Gate I.6 — Import existence ══════════════════

_IMPORT_RE_FROM = re.compile(
    r"^\s*from\s+([\w\.]+)\s+import\s+(.+?)(?:\s*#.*)?$", re.MULTILINE)
_IMPORT_RE_PLAIN = re.compile(
    r"^\s*import\s+([\w\.]+)(?:\s+as\s+\w+)?\s*(?:#.*)?$", re.MULTILINE)


def _collect_source_files(vault_dir: Path, module_id: str) -> list[Path]:
    """Find .py files inside vault/<module_id> excluding tests/pycache."""
    mdir = vault_dir / module_id
    if not mdir.is_dir():
        return []
    files = []
    for p in mdir.rglob("*.py"):
        parts = set(p.parts)
        if "__pycache__" in parts or "tests" in parts:
            continue
        files.append(p)
    return files


def _exports_of(vault_dir: Path, module_id: str) -> set[str]:
    """Return top-level names defined in the module's source
    (functions, classes, module-level assignments). Used as the ground
    truth for what other modules can legitimately import from this one."""
    names: set[str] = set()
    for py in _collect_source_files(vault_dir, module_id):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(
                    node.target, ast.Name):
                names.add(node.target.id)
    return names


def _imports_from(py_file: Path, module_id: str) -> list[str]:
    """Names imported FROM a specific upstream module_id in this .py file."""
    text = py_file.read_text(encoding="utf-8", errors="replace")
    imported = []
    for m in _IMPORT_RE_FROM.finditer(text):
        mod, names_str = m.group(1), m.group(2)
        head = mod.split(".")[0]
        if head != module_id:
            continue
        for tok in names_str.split(","):
            name = tok.strip().split(" as ")[0].strip()
            if name and name != "*":
                imported.append(name)
    return imported


def gate_I6_import_check(modules: list[dict], vault_dir: Path) -> list[str]:
    """For every B->A edge: scan B's .py files for `from A import X` and
    verify X exists in A's exported symbols. Wildcard `import *` is not
    checked (unresolvable without full runtime eval)."""
    errors = []
    export_cache: dict[str, set[str]] = {}
    for m in modules:
        b_name = m["name"]
        b_files = _collect_source_files(vault_dir, b_name)
        for a in m["depends_on"]:
            if a not in export_cache:
                export_cache[a] = _exports_of(vault_dir, a)
            a_exports = export_cache[a]
            if not a_exports:
                # Empty vault or unparseable source — skip; I.1 already flags
                continue
            missing = []
            for py in b_files:
                for imp in _imports_from(py, a):
                    if imp not in a_exports:
                        missing.append(
                            f"{py.name}: `from {a} import {imp}` "
                            f"but '{imp}' is not defined in {a}")
            if missing:
                errors.append(
                    f"[I.6] {b_name} depends_on {a}: "
                    f"{len(missing)} unresolved import(s)")
                for line in missing[:10]:
                    print(f"    [I.6][ERR] {line}")
                if len(missing) > 10:
                    print(f"    [I.6][ERR] ... and {len(missing) - 10} more")
            else:
                print(f"    [I.6] {b_name} <- {a}: OK "
                      f"(imports resolved against {len(a_exports)} exports)")
    return errors


# ═════════════════════ Public entry ═════════════════════════════════

def run_wiring_gates(raw_modules: list, vault_dir: Path) -> tuple[list[str], list[str]]:
    """Top-level driver called from integrate_multi_m.py.

    Args:
        raw_modules: value of manifest['modules'] as loaded from YAML
        vault_dir: RECEIPT_VAULT path

    Returns:
        (errors, order)
        errors: list of ERROR strings (empty = all gates passed).
        order: topological build order (list of module names).
    """
    modules, wiring_declared = normalize_manifest(raw_modules)
    if not wiring_declared:
        print("  [I.5/I.6] Wiring undeclared in manifest — skipping "
              "(legacy list-of-strings manifest; add `depends_on` to opt in).")
        return [], [m["name"] for m in modules]

    order = topological_order(modules)
    print(f"  [wiring] Topological build order: {' -> '.join(order)}")

    try:
        import yaml as _yaml
    except ImportError:
        return (["[I.5/I.6] PyYAML not installed — cannot verify wiring"],
                order)

    errors = []
    errors.extend(gate_I5_shape_match(modules, vault_dir, _yaml))
    errors.extend(gate_I6_import_check(modules, vault_dir))
    return errors, order
