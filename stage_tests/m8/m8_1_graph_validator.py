"""M8-1: Integration Graph Validator (M8_v2).

Overview
--------
This module validates an integration graph against a given module inventory.

Rules (locked behavior)
-----------------------
- Missing required node            => FAIL
- Unknown node (not in inventory)  => FAIL
- Edge endpoint not in nodes       => FAIL
- Declared graph signature mismatch (when provided) => FAIL
- Unknown keys in graph dict       => schema FAIL
- Type/shape violations            => system schema violation

Determinism
-----------
graph_signature is computed as:

    "sha256:" + sha256(
        canonical_json({
            "nodes": sorted(nodes),
            "edges": sorted_edges
        })
    )

Canonical JSON settings:
- sort_keys=True
- separators=(",", ":")
- ensure_ascii=False

Public API (DO NOT CHANGE signatures)
-------------------------------------
- validate_graph
- m8_1_validate_graph (alias)

Return Payload (I/O contract)
-----------------------------
A stable dict (superset for compatibility):

    {
        "graph_valid": bool,
        "graph_complete": bool,   # alias: equals graph_valid
        "graph_signature": str,   # "sha256:<64hex>"
        "reason_code": str | None
    }

Reason Codes (allowlisted)
--------------------------
- SYS_SCHEMA_VIOLATION
- M8_SCHEMA_FAIL
- M8_GRAPH_INCOMPLETE
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

# Allowlisted reason codes (REASON_CODES_M8.yaml)
REASON_SYS_SCHEMA_VIOLATION: Final[str] = "SYS_SCHEMA_VIOLATION"
REASON_M8_SCHEMA_FAIL: Final[str] = "M8_SCHEMA_FAIL"
REASON_M8_GRAPH_INCOMPLETE: Final[str] = "M8_GRAPH_INCOMPLETE"

_ALLOWED_GRAPH_KEYS: Final[set[str]] = {"nodes", "edges", "required_nodes"}


def _canonical_json_bytes(obj: Any) -> bytes:
    """Convert an object into canonical JSON bytes.

    Args:
        obj: Any JSON-serializable Python object.

    Returns:
        UTF-8 encoded bytes of canonical JSON, using:
        - sort_keys=True
        - separators=(",", ":")
        - ensure_ascii=False
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_prefixed(data: bytes) -> str:
    """Compute a sha256 hex digest and prefix with 'sha256:'.

    Args:
        data: Input bytes.

    Returns:
        A string of the form "sha256:<64hex>".
    """
    return "sha256:" + hashlib.sha256(data).hexdigest()


# Deterministic signature used for schema/system violations.
# NOTE: This constant is *not* a "success" signature; it is a stable fallback.
_INVALID_SIGNATURE: Final[str] = _sha256_prefixed(_canonical_json_bytes({"nodes": [], "edges": []}))


def _is_str_list(value: Any) -> bool:
    """Check whether a value is a list[str].

    Args:
        value: Any object.

    Returns:
        True if value is a list and every item is a string, else False.
    """
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _normalize_edges(edges: Any) -> list[list[str]]:
    """Normalize edges into a sorted list of [src, dst] pairs.

    Accepted input edges format:
    - list of 2-item list/tuple where both items are strings

    Behavior:
    - None => []
    - Any invalid shape/type => raises TypeError
    - Returned edges are sorted lexicographically by (src, dst)

    Args:
        edges: Raw edges input.

    Returns:
        Normalized, sorted edges in the form [[src, dst], ...].

    Raises:
        TypeError: If edges is not a list, or any edge is not a 2-item (list/tuple) of strings.
    """
    if edges is None:
        return []
    if not isinstance(edges, list):
        raise TypeError("edges must be a list")

    normalized: list[list[str]] = []
    for edge in edges:
        if (
            isinstance(edge, (list, tuple))
            and len(edge) == 2
            and isinstance(edge[0], str)
            and isinstance(edge[1], str)
        ):
            normalized.append([edge[0], edge[1]])
        else:
            raise TypeError("each edge must be a 2-item list/tuple of strings")

    normalized.sort(key=lambda pair: (pair[0], pair[1]))
    return normalized


def _extract_inventory_ids(module_inventory: Any) -> set[str]:
    """Extract module_id values from module_inventory.

    Schema expectations:
    - module_inventory must be a list[dict]
    - each dict must contain a non-empty string key "module_id"

    Args:
        module_inventory: Raw module inventory input.

    Returns:
        A set of module_id strings.

    Raises:
        TypeError: If module_inventory shape is invalid or module_id is missing/invalid.
    """
    if not isinstance(module_inventory, list):
        raise TypeError("module_inventory must be a list")

    module_ids: set[str] = set()
    for item in module_inventory:
        if not isinstance(item, dict):
            raise TypeError("each module_inventory item must be a dict")
        module_id = item.get("module_id")
        if not isinstance(module_id, str) or not module_id:
            raise TypeError("module_inventory items must have non-empty string 'module_id'")
        module_ids.add(module_id)

    return module_ids


def _result(*, graph_valid: bool, graph_signature: str, reason_code: str | None) -> dict[str, Any]:
    """Build a stable result payload.

    NOTE:
        This helper exists to keep the return shape consistent everywhere.
        It must not change key names or semantics (I/O contract).

    Args:
        graph_valid: Whether the graph is valid.
        graph_signature: Deterministic signature for this graph (or fallback signature on violation).
        reason_code: One of allowlisted reason codes, or None when valid.

    Returns:
        Result dict with keys:
        - graph_valid
        - graph_complete (alias: equals graph_valid)
        - graph_signature
        - reason_code
    """
    return {
        "graph_valid": graph_valid,
        "graph_complete": graph_valid,  # compatibility alias
        "graph_signature": graph_signature,
        "reason_code": reason_code,
    }


def validate_graph(
    module_inventory: list[dict[str, Any]],
    graph: dict[str, Any],
    *,
    artifact_refs: Any | None = None,
    declared_graph_signature: str | None = None,
) -> dict[str, Any]:
    """Validate integration graph completeness.

    The function enforces:
    1) Graph schema (unknown keys not allowed)
    2) Required nodes must exist in graph nodes
    3) Every node must exist in module_inventory
    4) Every edge endpoint must exist in graph nodes
    5) If declared_graph_signature is provided, it must match computed signature

    Args:
        module_inventory: List of module records. Each must contain "module_id".
        graph: Graph dict with keys:
            - nodes: list[str]
            - required_nodes: list[str]
            - edges: list[[src, dst], ...]
        artifact_refs: Kept for signature parity with higher-level orchestration (unused in M8-1).
        declared_graph_signature: Optional signature to verify against computed graph signature.

    Returns:
        A dict with keys:
        - graph_valid: bool
        - graph_complete: bool (alias; equals graph_valid)
        - graph_signature: str ("sha256:<64hex>")
        - reason_code: str | None

    Reason codes:
        - M8_SCHEMA_FAIL: unknown keys present in graph
        - M8_GRAPH_INCOMPLETE: graph fails validation rules
        - SYS_SCHEMA_VIOLATION: type/shape violations or unexpected schema errors
    """
    _ = artifact_refs  # unused by M8-1 (kept for signature parity)

    try:
        if not isinstance(graph, dict):
            raise TypeError("graph must be a dict")

        # Schema guard: unknown keys => schema fail (do not ignore)
        if (set(graph.keys()) - _ALLOWED_GRAPH_KEYS):
            return _result(
                graph_valid=False,
                graph_signature=_INVALID_SIGNATURE,
                reason_code=REASON_M8_SCHEMA_FAIL,
            )

        nodes_any = graph.get("nodes", [])
        required_nodes_any = graph.get("required_nodes", [])
        edges_any = graph.get("edges", [])

        if not _is_str_list(nodes_any) or not _is_str_list(required_nodes_any):
            raise TypeError("nodes/required_nodes must be list[str]")

        nodes: list[str] = nodes_any
        required_nodes: list[str] = required_nodes_any

        # Use set for fast membership checks.
        nodes_set = set(nodes)

        # Normalize/sort edges once (also validates type/shape).
        edges_norm = _normalize_edges(edges_any)

        # Deterministic signature:
        # - nodes sorted
        # - edges normalized & sorted
        nodes_sorted = sorted(nodes)
        graph_signature = _sha256_prefixed(_canonical_json_bytes({"edges": edges_norm, "nodes": nodes_sorted}))

        # Inventory set for unknown-node detection
        inventory_ids = _extract_inventory_ids(module_inventory)

        # 1) Missing required nodes => FAIL
        missing_required = set(required_nodes) - nodes_set
        if missing_required:
            # NOTE: reason_code semantics locked by tests/spec: use M8_GRAPH_INCOMPLETE
            return _result(
                graph_valid=False,
                graph_signature=graph_signature,
                reason_code=REASON_M8_GRAPH_INCOMPLETE,
            )

        # 2) Unknown nodes => FAIL (graph node not in inventory)
        unknown_nodes = nodes_set - inventory_ids
        if unknown_nodes:
            return _result(
                graph_valid=False,
                graph_signature=graph_signature,
                reason_code=REASON_M8_GRAPH_INCOMPLETE,
            )

        # 3) Edge endpoints must exist in nodes
        for src, dst in edges_norm:
            if src not in nodes_set or dst not in nodes_set:
                return _result(
                    graph_valid=False,
                    graph_signature=graph_signature,
                    reason_code=REASON_M8_GRAPH_INCOMPLETE,
                )

        # 4) Optional declared signature must match computed signature
        if declared_graph_signature is not None:
            if not isinstance(declared_graph_signature, str):
                raise TypeError("declared_graph_signature must be a string")
            if declared_graph_signature != graph_signature:
                return _result(
                    graph_valid=False,
                    graph_signature=graph_signature,
                    reason_code=REASON_M8_GRAPH_INCOMPLETE,
                )

        return _result(graph_valid=True, graph_signature=graph_signature, reason_code=None)

    except Exception:
        # Any type/shape violations => system schema violation (deterministic signature)
        return _result(
            graph_valid=False,
            graph_signature=_INVALID_SIGNATURE,
            reason_code=REASON_SYS_SCHEMA_VIOLATION,
        )


def m8_1_validate_graph(module_inventory: list[dict[str, Any]], graph: dict[str, Any]) -> dict[str, Any]:
    """Alias for validate_graph.

    This alias is kept for compatibility with harnesses that call the module-specific function.

    Args:
        module_inventory: See validate_graph.
        graph: See validate_graph.

    Returns:
        Same payload as validate_graph.
    """
    return validate_graph(module_inventory, graph)
