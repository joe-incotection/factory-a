"""
hallucination_gate.py — static "phantom name" detector (anti-hallucination).

Catches the classic AI failure: code that USES a name (variable / function / API)
it never defined, imported, or that isn't a builtin. Pure AST, deterministic,
0 LLM tokens. This is the "ดักตัวแปรหลอน" gate — a checkable hallucination the
gate can crush before tests even run.

Scope (honest): module-flat scope analysis — collects every name DEFINED anywhere
in the module (imports, def/class, params, assignments, loop/with/except targets,
comprehensions, walrus) and flags Load-names not in that set ∪ builtins. This
favours ZERO false positives (won't block valid code) over catching use-before-def.
It is NOT a full type/scope checker; it catches phantom names, which is the goal.
"""
from __future__ import annotations

import ast
import builtins
from typing import List, Set, Dict, Any

_BUILTINS: Set[str] = set(dir(builtins)) | {
    "__name__", "__file__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "self", "cls",
}


def _collect_defined(tree: ast.AST) -> Set[str]:
    """Every name bound anywhere in the module (flat scope)."""
    defined: Set[str] = set()

    def add_target(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            defined.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for e in node.elts:
                add_target(e)
        elif isinstance(node, ast.Starred):
            add_target(node.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                defined.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            a = node.args
            for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
                defined.add(arg.arg)
            if a.vararg:
                defined.add(a.vararg.arg)
            if a.kwarg:
                defined.add(a.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Lambda):
            a = node.args
            for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
                defined.add(arg.arg)
            if a.vararg:
                defined.add(a.vararg.arg)
            if a.kwarg:
                defined.add(a.kwarg.arg)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in tgts:
                add_target(t)
        elif isinstance(node, ast.NamedExpr):      # walrus :=
            add_target(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            add_target(node.target)
        elif isinstance(node, ast.comprehension):
            add_target(node.target)
        elif isinstance(node, ast.withitem):
            if node.optional_vars:
                add_target(node.optional_vars)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                defined.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
    return defined


def _has_star_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            return True
    return False


def find_phantom_names(source: str) -> List[str]:
    """Return sorted unique names USED but never defined/imported/builtin.

    If the module uses `from x import *`, its namespace is unknowable by static
    analysis, so we DO NOT flag (avoids false alarms on valid code) — returns []."""
    tree = ast.parse(source)
    if _has_star_import(tree):
        return []
    defined = _collect_defined(tree) | _BUILTINS
    used: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
    return sorted(used - defined)


def find_phantom_occurrences(source: str):
    """Return [{name, line, col}] for each USE of a phantom name (for inline diagnostics)."""
    tree = ast.parse(source)
    if _has_star_import(tree):
        return []
    defined = _collect_defined(tree) | _BUILTINS
    phantom = {n.id for n in ast.walk(tree)
               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - defined
    occ = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in phantom:
            occ.append({"name": n.id, "line": n.lineno, "col": n.col_offset})
    return occ


def gate(source: str) -> Dict[str, Any]:
    """PASS/FAIL verdict. FAIL lists phantom names + per-occurrence line/col."""
    try:
        phantom = find_phantom_names(source)
    except SyntaxError as e:
        return {"status": "FAIL", "reason_code": "RC_SYNTAX_ERROR",
                "phantom_names": [], "occurrences": [],
                "detail": f"line {e.lineno}: {e.msg}",
                "syntax_error": {"line": e.lineno or 1, "col": (e.offset or 1) - 1, "msg": e.msg}}
    if phantom:
        return {"status": "FAIL", "reason_code": "RC_HALLUCINATED_NAME",
                "phantom_names": phantom,
                "occurrences": find_phantom_occurrences(source),
                "detail": f"used but never defined/imported: {', '.join(phantom)}"}
    return {"status": "PASS", "reason_code": None, "phantom_names": [], "occurrences": []}


if __name__ == "__main__":
    CLEAN = '''
import math
def area(r):
    pi = math.pi
    return pi * r * r
class Box:
    def __init__(self, w, h):
        self.w, self.h = w, h
    def vol(self):
        return self.w * self.h
vals = [area(i) for i in range(3)]
total = sum(vals)
'''
    PHANTOM_VAR = '''
def f(x):
    return x * scale_factor   # scale_factor never defined -> phantom
'''
    PHANTOM_API = '''
import math
def g(r):
    return maths.pi * r   # typo'd module 'maths' (not imported) -> phantom
'''
    cases = [("clean", CLEAN, "PASS"), ("phantom_var", PHANTOM_VAR, "FAIL"),
             ("phantom_api", PHANTOM_API, "FAIL")]
    ok = True
    print("=== hallucination_gate self-test ===")
    for name, src, want in cases:
        r = gate(src)
        passed = r["status"] == want
        ok = ok and passed
        print(f"  [{name}] {'OK' if passed else 'XX'} -> {r['status']} {r.get('phantom_names') or ''}")
    print("RESULT:", "ALL PASS" if ok else "FAILURES")
    raise SystemExit(0 if ok else 1)
