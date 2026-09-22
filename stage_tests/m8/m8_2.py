"""M8-2: Invariant Engine (SSOT)

Evaluates invariants declared in the SSOT YAML file (`m8_invariants.yaml`).

Constraints (per spec/tests):
- Invariant definitions MUST live in YAML; do not hardcode invariant logic in code.
- Execution order MUST follow YAML order.
- Unknown / malformed invariant entries MUST be treated as failing.

Supported rule language (minimal, as required by golden tests):
- exists(<path>)
- <path> == <literal>

Where:
- <path> is a dotted path resolved against the provided context dict.
- <literal> supports: true/false (case-insensitive), numbers, and quoted strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


Context = Dict[str, Any]
Result = Dict[str, Any]


@dataclass(frozen=True, slots=True)
class _CompiledInvariant:
    """Internal representation of a compiled invariant.

    Attributes:
        inv_id: Invariant id from YAML. None means missing/invalid id.
        kind: The compiled rule type: "exists", "eq", or "unknown".
        path_parts: Pre-split dotted path parts for faster lookup in context.
        literal: Parsed literal for "eq" rules; otherwise None.
    """

    inv_id: Optional[str]
    kind: str  # "exists" | "eq" | "unknown"
    path_parts: Tuple[str, ...]
    literal: Any


_RULE_EXISTS_RE: Final[re.Pattern[str]] = re.compile(
    r"^exists\((?P<path>[A-Za-z_][A-Za-z0-9_\.\-]*)\)\s*$"
)
_RULE_EQ_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<path>[A-Za-z_][A-Za-z0-9_\.\-]*)\s*==\s*(?P<lit>.+?)\s*$"
)

# Cache compiled invariants by (absolute_path, mtime_ns, size).
# This speeds up repeated calls where the SSOT file is unchanged.
_CACHE: Dict[Tuple[str, int, int], List[_CompiledInvariant]] = {}


def _failure_result(reason: str) -> Result:
    """Build a hard-fail style result object.

    Args:
        reason: Machine-readable failure reason string.

    Returns:
        A result dict that matches the public I/O contract, with:
        - invariants_checked = 0
        - invariants_passed = 0
        - failed_invariants = [reason]
    """
    return {
        "invariants_checked": 0,
        "invariants_passed": 0,
        "failed_invariants": [reason],
    }


def _maybe_normalize_yaml_text(raw_text: str) -> str:
    """Normalize a narrow YAML formatting slip used by tests.

    This function does NOT define any invariant logic. It only helps parsing
    a specific formatting issue where `id` is split across lines:

        - id:
         INV1

    It is normalized to:

        - id: INV1

    Args:
        raw_text: Raw YAML text read from file.

    Returns:
        The original text (most cases) or a normalized variant if the slip is detected.
    """
    # Fast pre-check: only run the more expensive line-walk if pattern exists.
    if "- id:" not in raw_text:
        return raw_text

    lines = raw_text.splitlines()
    out_lines: List[str] = []
    i = 0
    changed = False
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(?P<prefix>\s*-\s+id:)\s*$", line)
        if m and (i + 1) < len(lines):
            nxt = lines[i + 1]
            val = nxt.strip()
            # Accept the next line if it's a plain scalar (after stripping).
            if val and not val.startswith("#") and ":" not in val:
                out_lines.append(f"{m.group('prefix')} {val}")
                changed = True
                i += 2
                continue
        out_lines.append(line)
        i += 1

    if not changed:
        return raw_text
    return "\n".join(out_lines) + ("\n" if raw_text.endswith("\n") else "")


def _get_by_parts(ctx: Context, parts: Tuple[str, ...]) -> Tuple[bool, Any]:
    """Resolve a pre-split dotted path inside a dict context.

    Args:
        ctx: Context dictionary to resolve from.
        parts: Tuple of keys representing a dotted path (e.g., ("a","b","c")).

    Returns:
        (found, value)
        - found: True if the full path exists; otherwise False.
        - value: Resolved value if found; otherwise None.
    """
    cur: Any = ctx
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _parse_literal(raw: str) -> Any:
    """Parse a literal token used in rule expressions.

    Supported literals:
      - true/false (case-insensitive) -> bool
      - quoted strings -> str (quotes removed)
      - integers -> int
      - floats/scientific -> float
      - otherwise -> str (raw token)

    Args:
        raw: Raw literal string captured from a rule.

    Returns:
        Parsed Python value representing the literal.
    """
    token = raw.strip()
    low = token.lower()

    if low == "true":
        return True
    if low == "false":
        return False

    # Quoted string.
    if len(token) >= 2 and (
        (token[0] == token[-1] == '"') or (token[0] == token[-1] == "'")
    ):
        return token[1:-1]

    # Integer.
    if re.fullmatch(r"[-+]?\d+", token):
        try:
            return int(token)
        except Exception:
            return token

    # Float / scientific notation.
    if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", token) or re.fullmatch(
        r"[-+]?\d+(?:[eE][-+]?\d+)", token
    ):
        try:
            return float(token)
        except Exception:
            return token

    # Fallback: keep as raw token string.
    return token


def _compile_rule(rule: str) -> Tuple[str, Tuple[str, ...], Any]:
    """Compile a rule string into an executable form.

    Args:
        rule: Rule expression string.

    Returns:
        (kind, path_parts, literal)
        - kind: "exists", "eq", or "unknown"
        - path_parts: tuple of keys for dotted path lookup
        - literal: parsed literal for "eq"; None otherwise
    """
    rule_str = rule.strip()

    m = _RULE_EXISTS_RE.match(rule_str)
    if m:
        parts = tuple(m.group("path").split("."))
        return "exists", parts, None

    m = _RULE_EQ_RE.match(rule_str)
    if m:
        parts = tuple(m.group("path").split("."))
        lit = _parse_literal(m.group("lit"))
        return "eq", parts, lit

    return "unknown", tuple(), None


def _compile_invariants(doc: Any) -> Tuple[bool, List[_CompiledInvariant]]:
    """Compile invariants from parsed YAML document.

    Notes:
        - This does NOT create or alter invariants.
        - It only compiles what is present in SSOT YAML into a faster structure.

    Args:
        doc: Parsed YAML document.

    Returns:
        (ok, compiled)
        - ok: False if YAML schema is invalid (e.g., missing invariants list).
        - compiled: Compiled invariants list preserving YAML order.
    """
    if not isinstance(doc, dict):
        return False, []
    raw_invariants = doc.get("invariants", [])
    if not isinstance(raw_invariants, list):
        return False, []

    compiled: List[_CompiledInvariant] = []
    for item in raw_invariants:
        if not isinstance(item, dict):
            # Preserve count; will be treated as unknown invariant id at runtime.
            compiled.append(
                _CompiledInvariant(
                    inv_id=None, kind="unknown", path_parts=tuple(), literal=None
                )
            )
            continue

        inv_id = item.get("id")
        rule = item.get("rule")

        # Missing/invalid id -> runtime will report UNKNOWN_INVARIANT_ID.
        if not isinstance(inv_id, str) or not inv_id.strip():
            compiled.append(
                _CompiledInvariant(inv_id=None, kind="unknown", path_parts=tuple(), literal=None)
            )
            continue

        # Missing/blank rule -> runtime will fail this invariant by id.
        if not isinstance(rule, str) or not rule.strip():
            compiled.append(
                _CompiledInvariant(inv_id=inv_id, kind="unknown", path_parts=tuple(), literal=None)
            )
            continue

        kind, parts, lit = _compile_rule(rule)
        compiled.append(_CompiledInvariant(inv_id=inv_id, kind=kind, path_parts=parts, literal=lit))

    return True, compiled


def _load_compiled_invariants(
    invariants_yaml_path: str,
) -> Tuple[Optional[List[_CompiledInvariant]], Optional[str]]:
    """Load and compile invariants from YAML with caching.

    Caching is keyed by (absolute_path, mtime_ns, size). If the file changes,
    it will be re-read and re-compiled.

    Args:
        invariants_yaml_path: Path to the invariants YAML file.

    Returns:
        (compiled_invariants, error_reason)
        - compiled_invariants: compiled invariants list if successful; else None.
        - error_reason: failure reason string if failed; else None.
    """
    p = Path(invariants_yaml_path)
    try:
        st = p.stat()
    except Exception:
        return None, "M8_YAML_PARSE_ERROR"

    key = (
        str(p.resolve()),
        getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
        int(st.st_size),
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached, None

    try:
        raw_text = p.read_text(encoding="utf-8")
        raw_text = _maybe_normalize_yaml_text(raw_text)
        doc = yaml.safe_load(raw_text)  # type: ignore[union-attr]
    except Exception:
        return None, "M8_YAML_PARSE_ERROR"

    ok, compiled = _compile_invariants(doc)
    if not ok:
        return None, "M8_INV_SCHEMA_ERROR"

    # Keep cache bounded: if it grows too much, drop everything (simple, fast).
    if len(_CACHE) > 32:
        _CACHE.clear()
    _CACHE[key] = compiled
    return compiled, None


def m8_2_run_invariants(invariants_yaml_path: str, context: Context) -> Result:
    """Run invariants from SSOT YAML file.

    Args:
        invariants_yaml_path: Path to m8_invariants.yaml (SSOT).
        context: Context dict containing computed results from earlier modules.

    Returns:
        Result dict with keys:
          - invariants_checked: int
          - invariants_passed: int
          - failed_invariants: list[str]
    """
    if yaml is None:
        return _failure_result("SYS_NO_YAML_LIB")

    compiled, err = _load_compiled_invariants(invariants_yaml_path)
    if err is not None or compiled is None:
        return _failure_result(err or "M8_YAML_PARSE_ERROR")

    failed: List[str] = []
    checked = 0
    passed = 0

    # Execution order preserved as YAML order.
    for inv in compiled:
        checked += 1

        inv_id = inv.inv_id
        if not isinstance(inv_id, str) or not inv_id.strip():
            failed.append("UNKNOWN_INVARIANT_ID")
            continue

        # Evaluate compiled rule kinds.
        if inv.kind == "exists":
            found, val = _get_by_parts(context, inv.path_parts)
            ok = found and bool(val)
        elif inv.kind == "eq":
            found, val = _get_by_parts(context, inv.path_parts)
            ok = found and (val == inv.literal)
        else:
            # Unknown syntax / malformed rule => treat as failing.
            ok = False

        if ok:
            passed += 1
        else:
            failed.append(inv_id)

    return {
        "invariants_checked": checked,
        "invariants_passed": passed,
        "failed_invariants": failed,
    }
