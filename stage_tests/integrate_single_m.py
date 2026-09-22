import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# ---- FORCE UTF-8 CONSOLE (Windows safe) ----
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# =========================================================
# Factory-A Single Module Integrator (PROPER FLOW)
# Flow: AIEL-T → Gate C → Vault → Bundle → M8/Stage2/M7
# =========================================================

ROOT = Path("C:/Factory-A")
MODULES_DEV = ROOT / "modules_dev"          # read-only: real module source

# ── SANDBOX ISOLATION (stage_tests_V2_patch) ─────────────────────────────────
# All write-paths redirected to sandbox. Real vault/outputs/stage_tests untouched.
SANDBOX_ROOT = Path(__file__).parent.resolve()  # C:\Factory-A\stage_tests_V2_patch
VAULT        = SANDBOX_ROOT / "vault"
OUTPUT       = SANDBOX_ROOT / "outputs" / "reports"
AIEL_T_DIR   = SANDBOX_ROOT / "aiel_t"
GATE_C_DIR   = SANDBOX_ROOT / "gate_c"
STAGE_RUNNER = SANDBOX_ROOT / "gate_runner.py"

# G-Score threshold (LAW 8 / Policy Rule C.3): modules must achieve >= 0.99.
# NOTE: Policy document states 0.95; all tools enforce 0.99 (stricter standard agreed by S1).
G_SCORE_THRESHOLD = 0.99

_IGNORE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_IGNORE_FILE_SUFFIXES = {".pyc", ".pyo"}


# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------
def clean_cache(folder: Path) -> None:
    """Remove common caches for deterministic runs."""
    for p in folder.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    for p in folder.rglob(".pytest_cache"):
        shutil.rmtree(p, ignore_errors=True)
    print(f"    ✅ Cache cleaned: {folder.name}")


def _check_law9_sys_path(test_dir: Path) -> None:
    """Scan test files for sys.path manipulation — LAW 9 violation.

    Golden test files must not manipulate sys.path. The pytest.ini
    pythonpath setting handles import resolution; any in-file sys.path
    override is forbidden by LAW 9.

    Patterns checked: sys.path.insert, sys.path.append,
                      sys.path.extend, sys.path[

    Raises:
        RuntimeError: PIPELINE_ABORT if any violation is found.
    """
    _LAW9_PATTERNS = (
        "sys.path.insert",
        "sys.path.append",
        "sys.path.extend",
        "sys.path[",
    )
    violations = []
    for test_file in sorted(test_dir.glob("*.py")):
        content = test_file.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # skip comment lines
            for pattern in _LAW9_PATTERNS:
                if pattern in line:
                    violations.append(f"  {test_file.name}:{line_no}: {stripped}")
    if violations:
        detail = "\n".join(violations)
        raise RuntimeError(
            f"PIPELINE_ABORT: LAW 9 violation — sys.path manipulation detected "
            f"in test files.\n"
            f"Use pytest.ini 'pythonpath' for import resolution, "
            f"not in-file sys.path overrides.\n"
            f"Violations:\n{detail}"
        )


def _write_pytest_ini(z: zipfile.ZipFile) -> None:
    """Make bundle root importable for pytest (Stage2 runs from extracted root)."""
    content = "\n".join(
        [
            "[pytest]",
            "pythonpath = .",
            "testpaths = tests",
            "python_files = test_*.py",
            "",
        ]
    )
    z.writestr("pytest.ini", content)


def _iter_files_deterministic(root: Path, *, exclude_dirnames: set[str] | None = None) -> list[Path]:
    """Return sorted file list under root, excluding caches and compiled artifacts."""
    exclude_dirnames = exclude_dirnames or set()
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if p.suffix.lower() in _IGNORE_FILE_SUFFIXES:
            continue
        parts = set(p.parts)
        if parts.intersection(_IGNORE_DIR_NAMES):
            continue
        if parts.intersection(exclude_dirnames):
            continue
        files.append(p)
    return sorted(files, key=lambda x: x.as_posix())


def _add_tree_to_zip(
    z: zipfile.ZipFile,
    src_root: Path,
    arc_root: str,
    *,
    exclude_dirnames: set[str] | None = None,
    exclude_filenames: set[str] | None = None,
) -> None:
    """Add directory tree to zip in deterministic order."""
    exclude_dirnames = exclude_dirnames or set()
    exclude_filenames = exclude_filenames or set()
    for f in _iter_files_deterministic(src_root, exclude_dirnames=exclude_dirnames):
        if f.name in exclude_filenames:
            continue
        rel = f.relative_to(src_root).as_posix()
        arcname = f"{arc_root}/{rel}" if rel else arc_root
        z.write(f, arcname=arcname)


def _require_one(glob_results: list[Path], label: str, where: Path) -> Path:
    if not glob_results:
        raise FileNotFoundError(f"{label} not found in {where}")
    return glob_results[0]


def _copy_once(src: Path, dst: Path) -> None:
    """Copy src to dst, raising FileExistsError if dst already exists.

    Enforces Policy Rule C.4 (write-once): vault artifacts may only be
    written once per integration run.  A second run must fail loudly
    rather than silently overwriting prior vault state.

    Args:
        src: Source file path.
        dst: Destination file path.

    Raises:
        FileExistsError: If dst already exists.
    """
    if dst.exists():
        raise FileExistsError(
            f"WRITE_ONCE_VIOLATION: {dst.name} already exists in vault.\n"
            f"  Path: {dst}\n"
            f"Archive or clear the prior vault entry before re-integrating."
        )
    shutil.copy2(src, dst)


def _find_python_package_dir(module_dir: Path, package_name: str) -> Path:
    """
    Find importable package dir for `package_name`.

    Acceptable layouts:
      0) module_dir itself IS the package:
         module_dir.name == package_name and module_dir/__init__.py exists
      1) module_dir/<package_name>/__init__.py
      2) module_dir/src/<package_name>/__init__.py
      3) Any nested <package_name>/__init__.py inside module_dir (fallback)
    """
    candidates: list[Path] = []

    if module_dir.name == package_name and (module_dir / "__init__.py").exists():
        candidates.append(module_dir)

    direct = module_dir / package_name / "__init__.py"
    if direct.exists():
        candidates.append(direct.parent)

    src = module_dir / "src" / package_name / "__init__.py"
    if src.exists():
        candidates.append(src.parent)

    for init_file in module_dir.rglob("__init__.py"):
        if init_file.parent.name == package_name:
            candidates.append(init_file.parent)

    if not candidates:
        raise FileNotFoundError(
            f"Package folder not found (searched: self, {package_name}/, src/{package_name}/, and nested). "
            f"Module dir: {module_dir}"
        )

    candidates = sorted(candidates, key=lambda p: len(p.relative_to(module_dir).parts) if p != module_dir else 0)
    chosen = candidates[0]
    print(f"    🔎 Package resolved: {chosen}")
    return chosen


def _parse_pytest_counts(stdout: str) -> tuple[int, int, int]:
    """
    Parse pytest summary line to get passed/failed/skipped counts.

    Handles both formats:
      -v  → counts " PASSED" / " FAILED" / " SKIPPED" per line
      -q  → parses summary "X passed, Y failed, Z skipped in ..."
    """
    # Try summary line first (works for both -v and -q)
    match_passed = re.search(r"(\d+) passed", stdout)
    match_failed = re.search(r"(\d+) failed", stdout)
    match_skipped = re.search(r"(\d+) skipped", stdout)

    passed = int(match_passed.group(1)) if match_passed else 0
    failed = int(match_failed.group(1)) if match_failed else 0
    skipped = int(match_skipped.group(1)) if match_skipped else 0

    # Fallback: count per-line markers (for -v mode)
    if passed == 0 and failed == 0:
        passed = stdout.count(" PASSED")
        failed = stdout.count(" FAILED")
        skipped = stdout.count(" SKIPPED")

    return passed, failed, skipped


# ---------------------------------------------------------
# Step 1: Run AIEL-T
# ---------------------------------------------------------
def run_aiel_t(module_id: str) -> Path:
    print("  [1/6] Running AIEL-T (Real pytest)...")
    module_dir = MODULES_DEV / module_id
    clean_cache(module_dir)
    test_dir = module_dir / "tests"
    if not test_dir.exists():
        raise FileNotFoundError(f"Tests not found: {test_dir}")
    _check_law9_sys_path(test_dir)  # LAW 9: abort before pytest if sys.path found

    # รัน pytest จาก ROOT เพื่อให้ import path ถูกต้อง
    cmd = ["pytest", str(test_dir), "--tb=short", "-q"]
    print(f"    🎯 Running: pytest {test_dir}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")

    passed, failed, skipped = _parse_pytest_counts(result.stdout)
    total = passed + failed + skipped

    # แสดง output จริงเพื่อ debug
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                print(f"    {line}")
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            if line.strip():
                print(f"    [stderr] {line}")

    # NO_TESTS hard-fail (Policy Section 6 / Gate C rule):
    # Zero collected tests = zero evidence. Gate C cannot issue a receipt
    # without test evidence. Abort here before writing any evidence artifact.
    if total == 0:
        raise RuntimeError(
            "PIPELINE_ABORT: NO_TESTS — pytest collected 0 tests.\n"
            "Gate C requires test evidence. Ensure the test file exists, "
            "is not empty, and matches the discovery pattern (test_*.py)."
        )

    evidence_data = {
        "module_id": module_id,
        "test_result": "PASS" if failed == 0 and total > 0 else ("FAIL" if failed > 0 else "NO_TESTS"),
        "tests_passed": passed,
        "tests_total": total,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "AIEL-T (real pytest execution)",
        "evidence_type": "SINGLE_MODULE_TEST",
    }

    evidence_path = AIEL_T_DIR / "evidence" / f"{module_id}_test_evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    if evidence_path.exists():
        raise FileExistsError(
            f"WRITE_ONCE_VIOLATION: Evidence file already exists: {evidence_path}\n"
            f"Archive or delete the prior AIEL-T evidence before re-integrating."
        )
    with open(evidence_path, "x", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    print(f"    ✅ AIEL-T Complete: {passed}/{total} tests passed")
    print(f"    ✅ Evidence saved: {evidence_path}")

    if failed > 0:
        raise RuntimeError(f"AIEL-T FAILED: {failed} tests failed. Fix code before integrating.")

    return evidence_path


# ---------------------------------------------------------
# Step 2: Gate C (stub receipt)
# ---------------------------------------------------------
def run_gate_c(evidence_path: Path, module_id: str) -> Path:
    print("  [2/6] Running Gate C (Receipt generation)...")

    with open(evidence_path, "r", encoding="utf-8") as f:
        evidence = json.load(f)

    receipt_data = {
        "module_id": module_id,
        "receipt_id": f"RECEIPT_{module_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "status": evidence.get("test_result", "UNKNOWN"),
        "evidence_ref": str(evidence_path.name),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gate_c_version": "1.0",
        "validator": "integrate_single_m.py (PROPER FLOW)",
    }

    receipt_path = GATE_C_DIR / "receipts" / f"{module_id}_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if receipt_path.exists():
        raise FileExistsError(
            f"WRITE_ONCE_VIOLATION: Receipt file already exists: {receipt_path}\n"
            f"Archive or delete the prior Gate C receipt before re-integrating."
        )
    with open(receipt_path, "x", encoding="utf-8") as f:
        json.dump(receipt_data, f, indent=2)

    print(f"    ✅ Gate C Complete: {receipt_data['status']}")
    print(f"    ✅ Receipt saved: {receipt_path}")
    return receipt_path


# ---------------------------------------------------------
# Step 3: Copy to Vault
# ---------------------------------------------------------
def copy_to_vault(module_id: str, evidence_path: Path, receipt_path: Path) -> None:
    print("  [3/6] Copying to Vault...")

    module_dir = MODULES_DEV / module_id
    vault_dir = VAULT / module_id
    vault_dir.mkdir(parents=True, exist_ok=True)

    _copy_once(evidence_path, vault_dir / "evidence.json")
    print("    ✅ evidence.json → vault")
    _copy_once(receipt_path, vault_dir / "receipt.json")
    print("    ✅ receipt.json → vault")

    lock_src = _require_one(list(module_dir.glob("*GOLDEN_IO_LOCK_*.yaml")), "*GOLDEN_IO_LOCK_*.yaml", module_dir)
    _copy_once(lock_src, vault_dir / lock_src.name)
    print(f"    ✅ {lock_src.name} → vault")

    reason_src = _require_one(list(module_dir.glob("*REASON_CODES*.yaml")), "*REASON_CODES*.yaml", module_dir)
    _copy_once(reason_src, vault_dir / reason_src.name)
    print(f"    ✅ {reason_src.name} → vault")

    test_src = module_dir / "tests"
    if test_src.exists():
        test_dest = vault_dir / "tests"
        test_dest.mkdir(parents=True, exist_ok=True)

        # Clear all stale *.py files from prior integration runs before
        # copying the current set.  Without this, renamed or deleted test
        # files accumulate in the vault and are included in the bundle,
        # causing duplicate or phantom test collection at Stage2.
        # (Root cause of MOOD-1 router failure: stale test_golden_router.py
        # co-existed with renamed test_golden_router_UPDATED_v2.py.)
        stale_files = sorted(test_dest.glob("*.py"))
        if stale_files:
            for stale in stale_files:
                stale.unlink()
                print(f"    🗑️  Removed stale: {stale.name}")
            print(f"    ✅ vault/tests/ cleared ({len(stale_files)} stale file(s) removed)")

        for test_file in sorted(test_src.glob("test_*.py"), key=lambda p: p.name):
            _copy_once(test_file, test_dest / test_file.name)
            print(f"    ✅ {test_file.name} → vault/tests/")

    print(f"    📁 Vault ready: {vault_dir}")


# ---------------------------------------------------------
# Step 4: Build Bundle
# ---------------------------------------------------------
def build_bundle(module_id: str) -> Path:
    print("  [4/6] Building Bundle...")

    vault_dir = VAULT / module_id
    bundle_path = vault_dir / f"{module_id}_SINGLE_bundle.zip"

    lock_src = _require_one(list(vault_dir.glob("*GOLDEN_IO_LOCK_*.yaml")), "*GOLDEN_IO_LOCK_*.yaml", vault_dir)
    reason_src = _require_one(list(vault_dir.glob("*REASON_CODES*.yaml")), "*REASON_CODES*.yaml", vault_dir)

    evidence_file = vault_dir / "evidence.json"
    receipt_file = vault_dir / "receipt.json"
    if not evidence_file.exists():
        raise FileNotFoundError(f"Missing evidence.json in vault: {evidence_file}")
    if not receipt_file.exists():
        raise FileNotFoundError(f"Missing receipt.json in vault: {receipt_file}")

    tests_dir = vault_dir / "tests"
    if not tests_dir.exists():
        raise FileNotFoundError(f"Vault tests not found: {tests_dir}")

    module_dir = MODULES_DEV / module_id
    pkg_dir = _find_python_package_dir(module_dir, module_id)

    exclude_dirs_for_pkg = {"tests", "evidence", "outputs"}
    exclude_files_for_pkg = {
        "pytest.ini",
        "manifest.json",
        lock_src.name,
        reason_src.name,
    }

    if bundle_path.exists():
        raise FileExistsError(
            f"WRITE_ONCE_VIOLATION: Bundle already exists: {bundle_path.name}\n"
            f"  Path: {bundle_path}\n"
            f"Archive or delete the prior bundle before re-integrating."
        )

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as z:
        manifest = {
            "module_inventory": [{"module_id": module_id, "version": "1.0"}],
            "graph": {"nodes": [module_id], "edges": [], "required_nodes": [module_id]},
        }
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        print("    ✅ manifest.json added")

        # Policy: module-local pytest.ini > ROOT (single-module gate)
        module_pytest_ini = module_dir / "pytest.ini"
        if module_pytest_ini.exists():
            z.write(module_pytest_ini, arcname="pytest.ini")
            print("    ✅ pytest.ini added (MODULE-LOCAL)")
        else:
            _write_pytest_ini(z)
            print("    ✅ pytest.ini added (ROOT)")

        z.write(lock_src, arcname=lock_src.name)
        print(f"    ✅ {lock_src.name} added (ROOT)")
        z.write(reason_src, arcname=reason_src.name)
        print(f"    ✅ {reason_src.name} added (ROOT)")

        _add_tree_to_zip(
            z,
            pkg_dir,
            module_id,
            exclude_dirnames=exclude_dirs_for_pkg,
            exclude_filenames=exclude_files_for_pkg,
        )
        print(f"    ✅ {module_id}/ package added (ROOT) from: {pkg_dir} (tests excluded)")

        for test_file in sorted(tests_dir.glob("test_*.py"), key=lambda p: p.name):
            z.write(test_file, arcname=f"tests/{test_file.name}")
            print(f"    ✅ tests/{test_file.name} added")

        evidence_folder = f"evidence/{module_id}/"
        z.write(evidence_file, arcname=f"{evidence_folder}evidence.json")
        print(f"    ✅ evidence/{module_id}/evidence.json added")
        z.write(receipt_file, arcname=f"{evidence_folder}receipt.json")
        print(f"    ✅ evidence/{module_id}/receipt.json added")

    print(f"    📦 Bundle created: {bundle_path.name}")
    print(f"    📦 Size: {bundle_path.stat().st_size:,} bytes")
    return bundle_path


# ---------------------------------------------------------
# Step 5: Run Pipeline
# ---------------------------------------------------------
def run_pipeline(bundle_path: Path, module_id: str) -> None:
    print("  [5/6] Running Gate Runner (M8 + Stage2 + M7)...")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / f"{module_id}_final_status.json"

    cmd = [sys.executable, str(STAGE_RUNNER), str(bundle_path), "--output", str(report_path)]

    print(f"    🎯 Command: python gate_runner.py {bundle_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if result.stdout:
        for line in result.stdout.split("\n"):
            if line.strip():
                print(f"    {line}")

    if result.stderr:
        for line in result.stderr.split("\n"):
            if line.strip():
                print(f"    [gate_runner stderr] {line}")

    if result.returncode != 0:
        raise RuntimeError(
            f"PIPELINE_ABORT: gate_runner.py exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

    print("  [6/6] Checking Results + G-Score Gate...")

    if not report_path.exists():
        raise RuntimeError(f"Report not created: {report_path}")

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    m8_status     = report.get("m8", {}).get("status", "UNKNOWN")
    stage2_status = report.get("stage2", {}).get("status", "UNKNOWN")
    final_status  = report.get("final_status", "UNKNOWN")
    g_score       = (report
                    .get("stage2", {})
                    .get("full_report", {})
                    .get("aggregation", {})
                    .get("repo_score", 0.0))

    print(f"    📊 M8 Status:     {m8_status}")
    print(f"    📊 Stage2 Status: {stage2_status}")
    print(f"    📊 Final Status:  {final_status}")
    print(f"    🎯 G-Score:       {g_score:.4f}")

    if g_score < G_SCORE_THRESHOLD:
        print("")
        print("  ╔══════════════════════════════════════════════════╗")
        print(f"  ║  FAIL: G-Score {g_score:.4f} < {G_SCORE_THRESHOLD}                    ║")
        print("  ║  Fix SOURCE CODE logic — NOT test file          ║")
        print("  ║  Re-run after fix                               ║")
        print("  ╚══════════════════════════════════════════════════╝")
        raise RuntimeError(f"G-SCORE GATE FAIL: {g_score:.4f} < {G_SCORE_THRESHOLD}")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("Factory-A Single Module Integrator (PROPER FLOW)")
    print("Flow: AIEL-T -> Gate C -> Vault -> Bundle -> M8/M7")
    print("=" * 60)

    # รับ module_id จาก argv (S3 ใช้) หรือ input (Human ใช้)
    if len(sys.argv) > 1:
        module_id = sys.argv[1].strip()
        print(f"Module ID (from argv): {module_id}")
    else:
        module_id = input("กรุณาใส่ชื่อ Module ID: ").strip()

    if not module_id:
        print("❌ No module ID provided")
        return

    module_dir = MODULES_DEV / module_id
    if not module_dir.exists():
        print(f"❌ Module not found: {module_dir}")
        return

    print(f"\n🚀 [Single Module Pipeline] Processing: {module_id}")
    print(f"  📂 Module directory: {module_dir}")

    try:
        evidence_path = run_aiel_t(module_id)
        receipt_path = run_gate_c(evidence_path, module_id)
        copy_to_vault(module_id, evidence_path, receipt_path)
        bundle_path = build_bundle(module_id)
        run_pipeline(bundle_path, module_id)

        print("\n" + "=" * 60)
        print(f"🏆 PIPELINE COMPLETE: {module_id}")
        print(f"📁 Vault: {VAULT / module_id}")
        print(f"📦 Bundle: {bundle_path}")
        print(f"📊 Report: {OUTPUT / f'{module_id}_final_status.json'}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

