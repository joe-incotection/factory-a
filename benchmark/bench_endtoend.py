"""
bench_endtoend.py — with-gate vs without: how many DEFECTS get shipped?

The headline credibility benchmark. A labeled set of tiny modules (clean + realistic
AI-failure classes) is run under three SHIP policies that mirror the market:

  TRUST     : ship if code is syntactically valid        (≈ "AI proposes, human accepts" / Cursor-style)
  CI_TESTS  : ship if the module's tests pass             (≈ ordinary CI)
  FACTORY_A : ship only if hallucination-gate PASS AND tests pass  (this product)

It actually RUNS the hallucination gate + pytest (deterministic, reproducible, 0 LLM tokens).
Lower "defects shipped" = better. The benchmark is HONEST: it includes a defect that even
Factory-A ships (semantic-silent with a weak test) — proving the lever is spec/test quality.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stage_tests" / "static_checks"))
from hallucination_gate import gate as hal_gate  # noqa: E402

# Each case: module source + its test. label: is it a defect that should be blocked?
CASES = [
    {
        "id": "clean",
        "defect": False, "klass": "—",
        "mod": "def mean(xs):\n    return sum(xs)/len(xs)\n",
        "test": "from m import mean\ndef test_mean():\n    assert mean([1,2,6])==3\n",
    },
    {
        "id": "phantom_untested",      # phantom name in a helper the test never calls
        "defect": True, "klass": "hallucinated name (untested path)",
        "mod": "def mean(xs):\n    return sum(xs)/len(xs)\n"
               "def scaled(xs):\n    return mean(xs)*FACTOR\n",   # FACTOR never defined
        "test": "from m import mean\ndef test_mean():\n    assert mean([2,4])==3\n",
    },
    {
        "id": "wrong_logic_tested",    # wrong code, test exercises it
        "defect": True, "klass": "wrong logic (tested)",
        "mod": "def mean(xs):\n    return sum(xs)*len(xs)\n",     # * instead of /
        "test": "from m import mean\ndef test_mean():\n    assert mean([1,2,6])==3\n",
    },
    {
        "id": "contract_violation_tested",  # output missing a required key; test checks schema
        "defect": True, "klass": "contract violation (tested)",
        "mod": "def summary(xs):\n    return {'mean': sum(xs)/len(xs)}\n",   # missing 'count'
        "test": "from m import summary\ndef test_keys():\n    r=summary([1,2,3])\n    assert 'mean' in r and 'count' in r\n",
    },
    {
        "id": "semantic_silent_weak_test",  # median mislabelled mean; test only symmetric
        "defect": True, "klass": "semantic-silent (weak test)",
        "mod": "def mean(xs):\n    s=sorted(xs)\n    return s[len(s)//2]\n",
        "test": "from m import mean\ndef test_mean():\n    assert mean([1,2,3])==2\n",  # 2==2 passes
    },
]

POLICIES = ["TRUST", "CI_TESTS", "FACTORY_A"]


def _syntactically_valid(src: str) -> bool:
    try:
        ast.parse(src); return True
    except SyntaxError:
        return False


def _tests_pass(d: Path) -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(d),
                       capture_output=True, text=True,
                       env={"PYTHONPATH": ".", **_os_environ()})
    return r.returncode == 0


def _os_environ():
    import os
    e = dict(os.environ); e["PYTHONIOENCODING"] = "utf-8"; return e


def ships(policy: str, src: str, hal_pass: bool, tests_pass: bool) -> bool:
    if policy == "TRUST":
        return _syntactically_valid(src)
    if policy == "CI_TESTS":
        return tests_pass
    if policy == "FACTORY_A":
        return hal_pass and tests_pass
    raise ValueError(policy)


def _print_kpi_mapping(shipped, total):
    """Tie each benchmark number to a buyer KPI — the 'so what' of the metric."""
    trust = shipped["TRUST"] / total if total else 0
    ci = shipped["CI_TESTS"] / total if total else 0
    fa = shipped["FACTORY_A"] / total if total else 0
    ci_reduction = (ci - fa) / ci if ci else 0
    print("\n--- WHAT KPI DOES THIS HELP? (metric -> buyer KPI -> why it matters) ---")
    print(f"  1. Escape rate {fa:.0%} (vs CI {ci:.0%}, vs trust {trust:.0%})")
    print(f"     KPI: PRODUCTION DEFECT / INCIDENT RATE. Factory-A cuts CI's escapes by {ci_reduction:.0%}")
    print(f"          -> fewer outages, less firefighting. The core 'reliability at scale' sell.")
    print( "  2. Defects caught PRE-MERGE (at the gate), not in prod")
    print( "     KPI: REWORK COST / DEBUG TIME. A bug caught at the gate is ~10-100x cheaper than in prod.")
    print( "  3. Gate cost = 0 LLM tokens (pure code) + RoundGuard ejects bad-spec loops")
    print( "     KPI: AI COGS / GROSS MARGIN. Verification adds ~no token cost (vs agent-reviews-agent),")
    print( "          and a hopeless spec is ejected (bounded burn) instead of looping forever.")
    print( "  4. Phantom-name detection (hallucinated var/API blocked)")
    print( "     KPI: HALLUCINATION RATE -> the headline differentiator vs Copilot/Cursor.")
    print( "  5. Every PASS emits a replayable receipt (capability, see M8/Gate-C)")
    print( "     KPI: AUDIT/COMPLIANCE PASS -> unlocks regulated buyers (finance/medical/safety).")


def run():
    shipped_defects = {p: 0 for p in POLICIES}
    rows = []
    total_defects = sum(1 for c in CASES if c["defect"])
    with tempfile.TemporaryDirectory() as tmp:
        for c in CASES:
            d = Path(tmp) / c["id"]
            d.mkdir()
            (d / "m.py").write_text(c["mod"], encoding="utf-8")
            (d / "test_m.py").write_text(c["test"], encoding="utf-8")
            hal_pass = hal_gate(c["mod"])["status"] == "PASS"
            tpass = _tests_pass(d)
            row = {"id": c["id"], "defect": c["defect"], "klass": c["klass"]}
            for p in POLICIES:
                s = ships(p, c["mod"], hal_pass, tpass)
                row[p] = "SHIP" if s else "BLOCK"
                if c["defect"] and s:
                    shipped_defects[p] += 1
            rows.append(row)

    print("=== Factory-A end-to-end benchmark: defects shipped (lower=better) ===")
    print(f"{'case':<28}{'defect_class':<30}{'TRUST':<8}{'CI_TESTS':<10}{'FACTORY_A'}")
    for r in rows:
        print(f"{r['id']:<28}{r['klass']:<30}{r['TRUST']:<8}{r['CI_TESTS']:<10}{r['FACTORY_A']}")
    print(f"\n--- DEFECTS SHIPPED / ESCAPE RATE (out of {total_defects}, lower=better) ---")
    for p in POLICIES:
        esc = shipped_defects[p] / total_defects if total_defects else 0
        print(f"  {p:<10}: {shipped_defects[p]}/{total_defects}   escape_rate={esc:.0%}")

    _print_kpi_mapping(shipped_defects, total_defects)

    print("\n--- HONEST notes (ห้ามอวย) ---")
    print("- TRUST ships every defect (no verification).")
    print("- CI_TESTS catches 'wrong_logic_tested' but ships defects on untested paths + weak tests.")
    print("- FACTORY_A adds the phantom-name gate -> also blocks 'phantom_untested' that CI ships.")
    print("- FACTORY_A STILL ships 'semantic_silent_weak_test': a median-as-mean bug whose test only")
    print("  checks a symmetric input. The gate is only as strong as the test -> the lever is")
    print("  spec/test quality (an oracle/asymmetric test would catch it). No 'zero bugs' claim.")
    print("- Tiny illustrative corpus; not a statistical study. Reproducible: re-run to verify.")
    return shipped_defects, total_defects


if __name__ == "__main__":
    run()
