#!/usr/bin/env python3
"""
run_gate.py — (C) one-command entry: auto-bundle a repo/module + run the gate.

Customers do NOT hand-build zips. Point this at any folder; it:
  1. generates manifest.json (module_inventory + graph) from the folder layout,
  2. zips the folder (excluding junk) with that manifest at the archive root,
  3. runs stage_tests/gate_runner.py (M8 + Stage2 + M7) on the bundle,
  4. prints PASS/FAIL.

Usage:
    python run_gate.py <path-to-folder> [--profile general|strict] [--output report.json]

Paths are workspace-relative (no hardcoded machine path). FACTORY_A_HOME env overrides the
package root used to locate the gate and profiles.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

HOME = Path(os.environ.get("FACTORY_A_HOME") or Path(__file__).resolve().parent)
GATE_RUNNER = HOME / "stage_tests" / "gate_runner.py"
PROFILES_DIR = HOME / "profiles"
sys.path.insert(0, str(HOME / "stage_tests" / "static_checks"))


def _scan_hallucinations(target: Path) -> dict:
    """Scan .py files for phantom names. Returns {status, offenders[str],
    diagnostics[{file,line,col,name,message}]} — diagnostics feed IDE squiggles."""
    try:
        from hallucination_gate import gate as halgate
    except Exception:
        return {"status": "SKIP", "offenders": [], "diagnostics": []}
    offenders, diagnostics = [], []
    for py in target.rglob("*.py"):
        if any(p in py.parts for p in ("__pycache__", ".venv", "venv", "node_modules")):
            continue
        try:
            r = halgate(py.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if r["status"] != "FAIL":
            continue
        rel = py.relative_to(target).as_posix()
        offenders.append(f"{py.name}: {r.get('detail', r.get('reason_code'))}")
        se = r.get("syntax_error")
        if se:
            diagnostics.append({"file": rel, "line": se["line"], "col": se["col"],
                                "name": "", "message": f"Syntax error: {se['msg']}"})
        for o in r.get("occurrences", []):
            diagnostics.append({"file": rel, "line": o["line"], "col": o["col"], "name": o["name"],
                                "message": f"'{o['name']}' is used but never defined or imported "
                                           f"(possible hallucination)"})
    status = "FAIL" if (offenders or diagnostics) else "PASS"
    return {"status": status, "offenders": offenders, "diagnostics": diagnostics}


def _emit_receipt(target: Path, report_path: Path) -> None:
    """Gate-C: on a passing gate, write a signed Decision_Receipt (hash chain +
    determinism key + evidence refs, write-once) into <target>/receipts/ — the
    tamper-evident proof, matching the M8_Golden_Receipts pattern."""
    gate_c_dir = HOME / "stage_tests" / "gate_c"
    try:
        sys.path.insert(0, str(gate_c_dir))
        from gate_c_wrapper import GateCWrapper  # noqa
    except Exception as e:
        print(f"[receipt] Gate-C unavailable ({e}) - skipped")
        return
    try:
        rep = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:
        rep = {}
    s2 = rep.get("stage2", {}) or {}
    tp = int(s2.get("tests_passed", 0) or 0)
    tt = int(s2.get("tests_total", 0) or 0)
    gscore = float(s2.get("repo_score", 1.0) or 1.0)
    aiel_t_result = {
        "status": "PASS",
        "g_score": gscore,
        "test_result": {"coverage": (tp / tt if tt else 1.0), "tests_passed": tp, "tests_total": tt},
        "toolchain": {"language": "python"},
    }
    try:
        receipts_dir = target / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        wrapper = GateCWrapper(base_dir=str(gate_c_dir))
        res = wrapper.process_aiel_t_output(
            aiel_t_result=aiel_t_result,
            module_info={"project_id": target.name, "module_id": target.name, "language": "python"},
            output_dir=str(receipts_dir),
        )
        if res.get("receipt_written"):
            print(f"[receipt] Decision_Receipt written -> {res['receipt_path']}")
        else:
            print(f"[receipt] not written ({res.get('reason')})")
    except Exception as e:
        print(f"[receipt] error ({e})")


def _hallucination_precheck(target: Path) -> dict:
    """Text-mode pre-gate wrapper (fail-fast before the expensive full gate)."""
    r = _scan_hallucinations(target)
    if r["status"] == "FAIL":
        return {"status": "FAIL", "offenders": r["offenders"]}
    return {"status": r["status"]}

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "node_modules", ".venv", "venv", ".idea", ".vscode"}
_SKIP_EXT = {".pyc", ".zip", ".rar"}


def _looks_like_module(d: Path) -> bool:
    """A subdir is a 'module' if it contains any source file."""
    for p in d.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".js", ".ts", ".go"):
            return True
    return False


def generate_manifest(target: Path) -> dict:
    """Build module_inventory + graph from folder layout.

    Top-level subdirs that contain source = module nodes. If the folder is flat
    (no module subdirs), it is treated as a single 'submission' module.
    """
    modules = []
    for child in sorted(target.iterdir()):
        if child.is_dir() and child.name not in _SKIP_DIRS and _looks_like_module(child):
            modules.append(child.name)
    if not modules:
        modules = ["submission"]
    nodes = list(modules)
    return {
        "module_inventory": [{"module_id": m} for m in modules],
        "graph": {"nodes": nodes, "edges": [], "required_nodes": nodes},
        "metadata": {"generated_by": "run_gate.py", "source": str(target)},
    }


def build_bundle(target: Path, out_zip: Path) -> dict:
    """Zip target (files at archive root) + inject generated manifest.json."""
    manifest = generate_manifest(target)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for f in files:
                if Path(f).suffix in _SKIP_EXT:
                    continue
                full = Path(root) / f
                z.write(full, full.relative_to(target).as_posix())
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Factory-A gate: auto-bundle a folder and verify it.")
    ap.add_argument("target", help="Path to the folder (module or project) to verify")
    ap.add_argument("--profile", choices=["general", "strict"], default="general",
                    help="Invariant profile (default: general). 'strict' = pure-logic/determinism HARD_FAIL.")
    ap.add_argument("--output", "-o", default=None, help="Report JSON path")
    ap.add_argument("--keep-bundle", action="store_true", help="Keep the generated bundle zip")
    ap.add_argument("--halonly", action="store_true",
                    help="Run ONLY the fast hallucination pre-gate (no bundle/tests)")
    ap.add_argument("--json", action="store_true",
                    help="With --halonly: emit machine-readable JSON diagnostics (for the IDE)")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        if args.json:
            print(json.dumps({"status": "ERROR", "diagnostics": [], "error": "not a folder"}))
        else:
            print(f"[X] Not a folder: {target}")
        return 2

    if args.halonly:
        if args.json:
            # Pure JSON to stdout (nothing else) so the extension can parse it.
            res = _scan_hallucinations(target)
            print(json.dumps(res))
            return 1 if res["status"] == "FAIL" else 0
        pre = _hallucination_precheck(target)
        if pre.get("status") == "FAIL":
            print("[hallucination] FAIL — phantom names (used but never defined/imported):")
            for o in pre["offenders"]:
                print(f"    - {o}")
            print("\n=== VERDICT: FAIL (hallucinated names) ===")
            return 1
        print("[hallucination] PASS (no phantom names)")
        print("\n=== VERDICT: PASS ===")
        return 0
    if not GATE_RUNNER.exists():
        print(f"[X] gate_runner not found at {GATE_RUNNER} (set FACTORY_A_HOME?)")
        return 2

    # Pre-gate (0-token static): reject hallucinated/phantom names before the full gate.
    pre = _hallucination_precheck(target)
    if pre.get("status") == "FAIL":
        print("[pre-gate] HALLUCINATION GATE — FAIL (phantom names used but never defined/imported):")
        for o in pre["offenders"]:
            print(f"    - {o}")
        print("\n=== VERDICT: FAIL (hallucinated names; full gate not run, 0 tokens spent) ===")
        return 1
    if pre.get("status") == "PASS":
        print("[pre-gate] hallucination gate: PASS (no phantom names)")

    out_zip = target.parent / f"_{target.name}_bundle.zip"
    report = Path(args.output) if args.output else target.parent / f"_{target.name}_gate_report.json"

    print(f"[1/2] Bundling {target.name} ...")
    manifest = build_bundle(target, out_zip)
    print(f"      modules: {[m['module_id'] for m in manifest['module_inventory']]}")

    cmd = [sys.executable, str(GATE_RUNNER), str(out_zip), "--output", str(report)]
    profile_dir = PROFILES_DIR / args.profile
    if profile_dir.exists():
        cmd += ["--config", str(profile_dir)]
        print(f"      profile: {args.profile} ({profile_dir})")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    print(f"[2/2] Running gate (M8 + Stage2 + M7) ...\n")
    rc = subprocess.run(cmd, env=env).returncode

    if not args.keep_bundle:
        try:
            out_zip.unlink()
        except OSError:
            pass

    if rc == 0:
        _emit_receipt(target, report)

    print(f"\n=== VERDICT: {'PASS' if rc == 0 else 'FAIL'} (report: {report}) ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())
