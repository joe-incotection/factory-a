# ===== File: C:\\Factory-A\integrate.py =====
import json
import os
import sys
import hashlib
import socket
import subprocess
from pathlib import Path

# ล็อกลายเซ็นเครื่องคุณโจ
AUTHORITY_LOCK_DIGEST = "6063b6928868b19778e0089364f6c63f580ff7ab36151ef49e90a22e3ea321eb"

JOE_ROOT = Path(r"C:\\Factory-A")

# ── SANDBOX ISOLATION (stage_tests_V2_patch) ─────────────────────────────────
# All write-paths redirected to sandbox. Real vault/outputs/stage_tests untouched.
SANDBOX_ROOT     = Path(__file__).parent.resolve()   # C:\Factory-A\stage_tests_V2_patch
STAGES_ROOT      = SANDBOX_ROOT
GATE_RUNNER_PATH = SANDBOX_ROOT / "gate_runner.py"

# G-Score threshold (LAW 8 / Policy Rule C.3): project must achieve >= 0.99.
# NOTE: Policy document states 0.95; all tools enforce 0.99 (stricter standard agreed by S1).
G_SCORE_THRESHOLD = 0.99

def verify_authority() -> bool:
    """Verify that this tool is running on Joe's authorized S1 machine.

    Computes SHA-256 of the machine hostname and compares against
    AUTHORITY_LOCK_DIGEST.  Raises RuntimeError on any mismatch so
    that the pipeline always aborts hard — a boolean return value alone
    is insufficient because callers could ignore it.

    Returns:
        True if and only if the runtime machine digest matches AUTHORITY_LOCK_DIGEST.

    Raises:
        RuntimeError: If machine identity cannot be verified.
    """
    print("🛡️ Verifying Authority Lock...")
    runtime_digest = hashlib.sha256(
        socket.gethostname().encode("utf-8")
    ).hexdigest()
    if runtime_digest != AUTHORITY_LOCK_DIGEST:
        raise RuntimeError(
            f"AUTHORITY_FAIL: Machine signature mismatch.\n"
            f"  Expected : {AUTHORITY_LOCK_DIGEST}\n"
            f"  Runtime  : {runtime_digest}\n"
            f"  Host     : {socket.gethostname()}\n"
            f"This tool requires S1 authority (Joe's authorized machine only)."
        )
    print("✅ Authority Lock verified.")
    return True

def auto_rebuild_pipeline():
    """Run integrate_multi_m.py in two explicit phases to build the project bundle.

    Phase 1 — COLLECT: verify all vault modules are present before assembly.
    Phase 2 — ASSEMBLE: merge single-module bundles into project_bundle.zip.

    Each phase is a separate subprocess call with --mode so failures are
    attributed to the correct phase.  Both stdout and stderr are captured and
    surfaced; non-zero exit codes abort the pipeline immediately.
    """
    print("🔄 [Auto-Pipeline] Building Project Bundle...")
    multi_m = SANDBOX_ROOT / "integrate_multi_m.py"
    if not multi_m.exists():
        raise RuntimeError(
            f"PIPELINE_ABORT: integrate_multi_m.py not found at {multi_m}"
        )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Phase 1: COLLECT — verify all vault modules are present
    print("🔄 [Auto-Pipeline] Step 1/2: COLLECT (verify vault)...")
    result_collect = subprocess.run(
        [sys.executable, str(multi_m), "--mode", "COLLECT"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result_collect.stdout:
        print(result_collect.stdout)
    if result_collect.stderr:
        print(f"[integrate_multi_m COLLECT stderr]\n{result_collect.stderr}")
    if result_collect.returncode != 0:
        raise RuntimeError(
            f"PIPELINE_ABORT: integrate_multi_m.py --mode COLLECT failed with exit code "
            f"{result_collect.returncode}.\nstderr: {result_collect.stderr}"
        )

    # Phase 2: ASSEMBLE — merge bundles into project_bundle.zip
    print("🔄 [Auto-Pipeline] Step 2/2: ASSEMBLE (merge bundles)...")
    result_assemble = subprocess.run(
        [sys.executable, str(multi_m), "--mode", "ASSEMBLE"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result_assemble.stdout:
        print(result_assemble.stdout)
    if result_assemble.stderr:
        print(f"[integrate_multi_m ASSEMBLE stderr]\n{result_assemble.stderr}")
    if result_assemble.returncode != 0:
        raise RuntimeError(
            f"PIPELINE_ABORT: integrate_multi_m.py --mode ASSEMBLE failed with exit code "
            f"{result_assemble.returncode}.\nstderr: {result_assemble.stderr}"
        )

    print("✅ Project Bundle step completed.")

def main():
    try:
        verify_authority()
    except RuntimeError as e:
        print(f"❌ Authority Verification Failed!\n{e}")
        sys.exit(1)

    # ดึงของใหม่มาอัปเดต
    auto_rebuild_pipeline()

    bundle_path = SANDBOX_ROOT / "integrated_project" / "project_bundle.zip"
    
    if not bundle_path.exists():
        print(f"❌ Bundle not found: {bundle_path}")
        print(f"   Please run 'python integrate_multi_m.py' first to create the bundle")
        return
    
    print(f"🚀 Launching Final Gate (M8/M7)...")
    print(f"📦 Using Bundle: {bundle_path}")
    
    final_out = SANDBOX_ROOT / "outputs" / "reports" / "project_final_report.json"
    final_out.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎯 Running Gate Runner on integrated project...")
    
    # บังคับ Encoding เป็น UTF-8 
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    cmd = [sys.executable, str(GATE_RUNNER_PATH), str(bundle_path), "--output", str(final_out)]
    
    # รัน M8/M7 
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"[gate_runner stderr]\n{result.stderr}")

    if result.returncode != 0:
        raise RuntimeError(
            f"PIPELINE_ABORT: gate_runner.py failed with exit code "
            f"{result.returncode}.\nstderr: {result.stderr}"
        )

    if not final_out.exists():
        raise RuntimeError(
            f"PIPELINE_ABORT: Final report not created at {final_out}"
        )

    print(f"🏆 FINAL REPORT CREATED: {final_out}")
    with open(final_out, "r", encoding="utf-8") as f:
        report = json.load(f)

    status = report.get("final_status", "UNKNOWN")
    print(f"📊 FINAL STATUS: {status}")

    # G-Score gate (LAW 8 / Policy Rule C.3): project G-Score must be >= 0.99.
    # NOTE: top-level final_status can be overridden to PASS by context_gate
    # even when the numeric G-Score is below threshold. We always check the
    # numeric score directly from stage2.repo_score.
    g_score = report.get("stage2", {}).get("repo_score")
    if g_score is None:
        raise RuntimeError(
            "PIPELINE_ABORT: G-Score not found in final report "
            "(expected report['stage2']['repo_score'])."
        )

    print(f"📊 G-Score: {g_score:.4f}")

    if g_score < G_SCORE_THRESHOLD:
        # Surface per-module G-Score breakdown to aid debugging.
        modules = (
            report.get("stage2", {})
                  .get("full_report", {})
                  .get("modules", [])
        )
        failing = [
            f"  {m.get('descriptor', {}).get('module_id', '?')}: "
            f"G={m.get('module_g_score', '?')}"
            for m in modules
            if isinstance(m.get("module_g_score"), (int, float))
            and m["module_g_score"] < G_SCORE_THRESHOLD
        ]
        detail = (
            "\n".join(failing) if failing
            else "  (no per-module breakdown available)"
        )
        raise RuntimeError(
            f"PIPELINE_ABORT: Project G-Score {g_score:.4f} < {G_SCORE_THRESHOLD} threshold "
            f"(LAW 8 / Policy Rule C.3).\n"
            f"Failing modules:\n{detail}"
        )

    print(f"✅ G-Score gate passed: {g_score:.4f} >= {G_SCORE_THRESHOLD}")

if __name__ == "__main__":
    main()
