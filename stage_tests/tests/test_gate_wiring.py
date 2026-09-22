"""pytest suite for stage_tests/gate_wiring.py — I.5 + I.6 + topological sort.

Run:
    python -m pytest factory_a_pkg/stage_tests/tests/test_gate_wiring.py -v

Covers:
  - normalize_manifest: legacy list-of-strings, new list-of-dicts, mixed,
                        duplicates, malformed entries
  - topological_order:  empty, single, chain, diamond, cycle, missing dep,
                        self-dep
  - gate_I5_shape_match: subset OK, missing field, empty contracts,
                          missing GOLDEN_IO_LOCK (silent skip)
  - gate_I6_import_check: resolved import, hallucinated import, no source,
                           import *, unrelated imports
  - run_wiring_gates:    legacy skip path + happy path + failure path
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add source root so we can import stage_tests.gate_wiring
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from stage_tests.gate_wiring import (  # noqa: E402
    normalize_manifest,
    topological_order,
    gate_I5_shape_match,
    gate_I6_import_check,
    run_wiring_gates,
    _shape_of,
    _required_set,
)


# ═════════════════════ normalize_manifest ═══════════════════════════

class TestNormalizeManifest:
    def test_legacy_list_of_strings(self):
        modules, wiring = normalize_manifest(["a", "b", "c"])
        assert wiring is False
        assert [m["name"] for m in modules] == ["a", "b", "c"]
        assert all(m["depends_on"] == [] for m in modules)

    def test_new_list_of_dicts(self):
        modules, wiring = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        assert wiring is True
        assert modules[1]["depends_on"] == ["a"]

    def test_mixed_strings_and_dicts(self):
        modules, wiring = normalize_manifest([
            "a", {"name": "b", "depends_on": ["a"]}])
        assert wiring is True
        assert modules[0]["name"] == "a"
        assert modules[0]["depends_on"] == []

    def test_dict_without_depends_on_is_not_wiring_declared(self):
        _, wiring = normalize_manifest([{"name": "a"}, {"name": "b"}])
        assert wiring is False

    def test_duplicate_name_raises(self):
        with pytest.raises(RuntimeError, match="duplicate module"):
            normalize_manifest(["a", "a"])

    def test_empty_name_raises(self):
        with pytest.raises(RuntimeError, match="missing 'name'"):
            normalize_manifest([{"name": ""}])

    def test_non_string_entry_raises(self):
        with pytest.raises(RuntimeError, match="must be str or dict"):
            normalize_manifest([123])

    def test_depends_on_not_list_raises(self):
        with pytest.raises(RuntimeError, match="depends_on"):
            normalize_manifest([{"name": "a", "depends_on": "b"}])

    def test_depends_on_empty_string_raises(self):
        with pytest.raises(RuntimeError, match="depends_on"):
            normalize_manifest([{"name": "a", "depends_on": [""]}])


# ═════════════════════ topological_order ════════════════════════════

class TestTopologicalOrder:
    def test_empty(self):
        assert topological_order([]) == []

    def test_single_module(self):
        modules, _ = normalize_manifest([{"name": "a"}])
        assert topological_order(modules) == ["a"]

    def test_linear_chain(self):
        modules, _ = normalize_manifest([
            {"name": "a"},
            {"name": "b", "depends_on": ["a"]},
            {"name": "c", "depends_on": ["b"]},
        ])
        assert topological_order(modules) == ["a", "b", "c"]

    def test_diamond_dependency(self):
        modules, _ = normalize_manifest([
            {"name": "root"},
            {"name": "left", "depends_on": ["root"]},
            {"name": "right", "depends_on": ["root"]},
            {"name": "join", "depends_on": ["left", "right"]},
        ])
        order = topological_order(modules)
        assert order.index("root") < order.index("left")
        assert order.index("root") < order.index("right")
        assert order.index("left") < order.index("join")
        assert order.index("right") < order.index("join")

    def test_cycle_raises(self):
        modules, _ = normalize_manifest([
            {"name": "a", "depends_on": ["b"]},
            {"name": "b", "depends_on": ["a"]},
        ])
        with pytest.raises(RuntimeError, match="cycle detected"):
            topological_order(modules)

    def test_missing_dep_raises(self):
        modules, _ = normalize_manifest([
            {"name": "a", "depends_on": ["ghost"]}])
        with pytest.raises(RuntimeError, match="not in the manifest"):
            topological_order(modules)

    def test_self_dependency_detected_as_cycle(self):
        modules, _ = normalize_manifest([
            {"name": "a", "depends_on": ["a"]}])
        with pytest.raises(RuntimeError, match="cycle"):
            topological_order(modules)

    def test_manifest_order_does_not_matter(self):
        # b listed first but depends on a
        modules, _ = normalize_manifest([
            {"name": "b", "depends_on": ["a"]},
            {"name": "a"},
        ])
        assert topological_order(modules) == ["a", "b"]


# ═════════════════════ Gate I.5 — shape match ═══════════════════════

@pytest.fixture
def vault_factory(tmp_path):
    """Factory that builds a vault dir with GOLDEN_IO_LOCK files."""
    def _make(specs: dict) -> Path:
        """specs = {module_id: yaml_text}"""
        for mid, txt in specs.items():
            d = tmp_path / mid
            d.mkdir(parents=True, exist_ok=True)
            (d / f"GOLDEN_IO_LOCK_{mid.upper()}.yaml").write_text(
                txt, encoding="utf-8")
        return tmp_path
    return _make


class TestGateI5ShapeMatch:
    def test_subset_ok(self, vault_factory):
        yaml_lib = pytest.importorskip("yaml")
        vault = vault_factory({
            "a": "output_contract:\n  required: [x, y]\n",
            "b": "input_contract:\n  required: [x]\n",
        })
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I5_shape_match(modules, vault, yaml_lib)
        assert errs == []

    def test_missing_field_flagged(self, vault_factory):
        yaml_lib = pytest.importorskip("yaml")
        vault = vault_factory({
            "a": "output_contract:\n  required: [x]\n",
            "b": "input_contract:\n  required: [y]\n",
        })
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I5_shape_match(modules, vault, yaml_lib)
        assert len(errs) == 1
        assert "[I.5]" in errs[0]
        assert "'y'" in errs[0]

    def test_empty_output_contract_flags_missing_fields(self, vault_factory):
        yaml_lib = pytest.importorskip("yaml")
        vault = vault_factory({
            "a": "output_contract: {}\n",
            "b": "input_contract:\n  required: [x]\n",
        })
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I5_shape_match(modules, vault, yaml_lib)
        assert len(errs) == 1

    def test_missing_lock_file_silent_skip(self, tmp_path):
        yaml_lib = pytest.importorskip("yaml")
        # neither module has a GOLDEN_IO_LOCK — I.1 catches this;
        # I.5 must silently skip to avoid duplicate flags
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I5_shape_match(modules, tmp_path, yaml_lib)
        assert errs == []


# ═════════════════════ Gate I.6 — import existence ══════════════════

class TestGateI6ImportCheck:
    def test_resolved_import_ok(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "a_source.py").write_text(
            "def hello():\n    return 1\n", encoding="utf-8")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "b_source.py").write_text(
            "from a import hello\n", encoding="utf-8")
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I6_import_check(modules, tmp_path)
        assert errs == []

    def test_hallucinated_import_flagged(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "a_source.py").write_text(
            "def real_fn():\n    return 1\n", encoding="utf-8")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "b_source.py").write_text(
            "from a import fake_fn\n", encoding="utf-8")
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I6_import_check(modules, tmp_path)
        assert len(errs) == 1
        assert "[I.6]" in errs[0]

    def test_unrelated_imports_ignored(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "a_source.py").write_text(
            "def hello():\n    return 1\n", encoding="utf-8")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "b_source.py").write_text(
            "import os\nfrom pathlib import Path\n",
            encoding="utf-8")
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I6_import_check(modules, tmp_path)
        assert errs == []

    def test_no_source_files_skip(self, tmp_path):
        # empty vault — nothing to check
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        modules, _ = normalize_manifest([
            {"name": "a"}, {"name": "b", "depends_on": ["a"]}])
        errs = gate_I6_import_check(modules, tmp_path)
        assert errs == []


# ═════════════════════ run_wiring_gates (integration) ═══════════════

class TestRunWiringGates:
    def test_legacy_manifest_skips(self, tmp_path):
        errs, order = run_wiring_gates(["a", "b"], tmp_path)
        assert errs == []
        assert order == ["a", "b"]

    def test_declared_wiring_happy_path(self, tmp_path):
        pytest.importorskip("yaml")
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "GOLDEN_IO_LOCK_A.yaml").write_text(
            "output_contract:\n  required: [x]\n", encoding="utf-8")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "GOLDEN_IO_LOCK_B.yaml").write_text(
            "input_contract:\n  required: [x]\n", encoding="utf-8")
        errs, order = run_wiring_gates(
            [{"name": "a"}, {"name": "b", "depends_on": ["a"]}],
            tmp_path)
        assert errs == []
        assert order == ["a", "b"]

    def test_declared_wiring_failure_path(self, tmp_path):
        pytest.importorskip("yaml")
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "GOLDEN_IO_LOCK_A.yaml").write_text(
            "output_contract:\n  required: [x]\n", encoding="utf-8")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "GOLDEN_IO_LOCK_B.yaml").write_text(
            "input_contract:\n  required: [y]\n", encoding="utf-8")
        errs, _ = run_wiring_gates(
            [{"name": "a"}, {"name": "b", "depends_on": ["a"]}],
            tmp_path)
        assert any("[I.5]" in e for e in errs)


# ═════════════════════ helpers ══════════════════════════════════════

class TestHelpers:
    def test_shape_of_object(self):
        assert _shape_of({"type": "object"}) == "object"

    def test_shape_of_array_of_number(self):
        assert _shape_of({"type": "array", "items": {"type": "number"}}) \
            == "array<number>"

    def test_shape_of_nested_array(self):
        s = _shape_of({"type": "array",
                       "items": {"type": "array",
                                 "items": {"type": "string"}}})
        assert s == "array<array<string>>"

    def test_required_set_normal(self):
        assert _required_set({"required": ["a", "b"]}) == {"a", "b"}

    def test_required_set_absent(self):
        assert _required_set({}) == set()

    def test_required_set_non_string_filtered(self):
        assert _required_set({"required": ["a", 42, "b"]}) == {"a", "b"}
