"""
aiel_runner.py — the AIEL-0→3 orchestrator as a product component (not a manual demo).

Drives a pluggable AI through the build stages, runs the deterministic gate, and on
failure BOUNCES back to the right stage with the reason — looping under a RoundGuard
(eject if the spec/logic is the real problem). This is the "plug in the customer's AI
→ run the pipeline" piece.

The AI is pluggable: any object with
    .generate(stage: str, spec: dict, files: dict, feedback: dict|None) -> dict[name,src]
Wire it to the customer's AI (VS Code LM API / ODE channel / API). The orchestration,
gate, bounce and round-guard are deterministic and live here (0 trust in the AI).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "stage_tests" / "static_checks"))
from hallucination_gate import gate as hal_gate   # noqa: E402
from round_guard import RoundGuard                # noqa: E402

BUILD_STAGES = ["AIEL-0", "AIEL-1", "AIEL-2", "AIEL-3"]

# reason_code -> stage to bounce back to (per FULL_PIPELINE_POLICY routing)
BOUNCE = {
    "RC_HALLUCINATED_NAME": "AIEL-2",   # correctness layer
    "RC_SYNTAX_ERROR": "AIEL-0",        # interpretation/skeleton
    "RC_TEST_FAILED": "AIEL-2",
}


def default_gate(files: Dict[str, str]) -> Dict[str, Any]:
    """Deterministic in-proc gate (hallucination pre-gate over .py).

    Production wires this to the full run_gate.py (tests + replay + receipt). Returns
    {status, reason_code, bounce_stage, detail}.
    """
    for name, src in files.items():
        if not name.endswith(".py"):
            continue
        r = hal_gate(src)
        if r["status"] == "FAIL":
            return {"status": "FAIL", "reason_code": r["reason_code"],
                    "bounce_stage": BOUNCE.get(r["reason_code"], "AIEL-2"),
                    "detail": f"{name}: {r.get('detail')}"}
    return {"status": "PASS", "reason_code": None}


def run_pipeline(spec: Dict[str, Any], ai, *, max_rounds: int = 3, gate=default_gate) -> Dict[str, Any]:
    """Build via AIEL-0→3, gate, bounce-and-fix under a RoundGuard. Returns a verdict dict."""
    log = []
    files: Dict[str, str] = {}

    # Initial build pass: AIEL-0 -> 1 -> 2 -> 3
    for stage in BUILD_STAGES:
        out = ai.generate(stage, spec, files, None)
        if out:
            files.update(out)
        log.append({"event": "build", "stage": stage})

    guard = RoundGuard(max_rounds=max_rounds)
    while True:
        result = gate(files)
        rec = guard.record(passed=(result["status"] == "PASS"),
                           tokens=result.get("tokens", 0))
        log.append({"event": "gate", "round": rec["round"],
                    "status": result["status"], "reason": result.get("reason_code")})

        if rec["action"] == "ACCEPT":
            return {"status": "CERTIFIED", "rounds": rec["round"],
                    "token_burn": rec["tokens_total"], "files": files, "log": log}

        if rec["action"] == "EJECT":
            return {"status": "EJECTED", "rounds": rec["round"],
                    "token_burn": rec["tokens_total"],
                    "reason_code": rec["reason_code"], "verdict": rec["verdict"], "log": log}

        # RETRY: bounce to the indicated stage with the gate's feedback
        bounce = result.get("bounce_stage", "AIEL-2")
        log.append({"event": "bounce", "to": bounce, "because": result.get("detail")})
        out = ai.generate(bounce, spec, files, result)
        if out:
            files.update(out)


# ----------------------------- self-test (mock AI) -----------------------------
_PHANTOM = "def scaled(xs):\n    return sum(xs)/len(xs)*FACTOR\n"
_FIXED = "FACTOR = 2\ndef scaled(xs):\n    return sum(xs)/len(xs)*FACTOR\n"


class _MockFixingAI:
    """Emits phantom code first; once bounced (feedback given), emits the fixed code."""
    def generate(self, stage, spec, files, feedback):
        if feedback is not None:                 # bounced -> apply the fix (any stage)
            return {"m.py": _FIXED}
        return {"m.py": _PHANTOM} if stage == "AIEL-0" else {}


class _MockStubbornAI:
    """Never fixes -> phantom forever -> RoundGuard must EJECT."""
    def generate(self, stage, spec, files, feedback):
        return {"m.py": "def scaled(xs):\n    return sum(xs)*FACTOR\n"} if stage == "AIEL-0" else {}


if __name__ == "__main__":
    spec = {"module": "demo", "entry": "scaled"}
    ok = True

    r1 = run_pipeline(spec, _MockFixingAI(), max_rounds=3)
    caseA = r1["status"] == "CERTIFIED"
    ok = ok and caseA
    print(f"[fixing-AI]   {'OK' if caseA else 'XX'} -> {r1['status']} after {r1['rounds']} gate round(s)")

    r2 = run_pipeline(spec, _MockStubbornAI(), max_rounds=3)
    caseB = r2["status"] == "EJECTED" and r2["reason_code"] == "RC_SPEC_LIKELY_WRONG"
    ok = ok and caseB
    print(f"[stubborn-AI] {'OK' if caseB else 'XX'} -> {r2['status']} ({r2.get('reason_code')}) after {r2['rounds']} rounds")

    print("RESULT:", "ALL PASS" if ok else "FAILURES")
    raise SystemExit(0 if ok else 1)
