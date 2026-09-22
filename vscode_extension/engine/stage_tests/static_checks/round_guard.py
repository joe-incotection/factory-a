"""
round_guard.py — fix-loop circuit breaker + token-burn meter.

Principle (Joe): if the AIEL fix loop can't pass the gate within N rounds, the
problem is NOT the code — it's the SPEC/LOGIC. Don't brute-force (burning tokens);
EJECT and tell the human to fix the spec. Also tracks cumulative token burn so the
loop's cost is visible.

Deterministic, reusable component to wire into any AIEL-0→3 orchestrator loop.
"""
from __future__ import annotations

from typing import Dict, Any, Optional


class RoundGuard:
    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.round = 0
        self.tokens_total = 0
        self.history = []

    def record(self, passed: bool, tokens: int = 0, reason: Optional[str] = None) -> Dict[str, Any]:
        """Record one fix round. Returns verdict incl. whether to EJECT.

        passed: did the gate PASS this round?
        tokens: tokens burned this round (token-burn meter).
        """
        self.round += 1
        self.tokens_total += max(0, int(tokens))
        self.history.append({"round": self.round, "passed": passed,
                              "tokens": tokens, "reason": reason})

        if passed:
            return {"action": "ACCEPT", "round": self.round,
                    "tokens_total": self.tokens_total,
                    "verdict": "PASS", "eject": False}

        if self.round >= self.max_rounds:
            return {
                "action": "EJECT",
                "round": self.round,
                "tokens_total": self.tokens_total,
                "eject": True,
                "reason_code": "RC_SPEC_LIKELY_WRONG",
                "verdict": (f"Exceeded {self.max_rounds} fix rounds without passing — "
                            f"the SPEC/LOGIC is likely wrong, not the code. "
                            f"Fix the spec and resubmit. (token burn: {self.tokens_total})"),
            }

        return {"action": "RETRY", "round": self.round,
                "tokens_total": self.tokens_total,
                "remaining": self.max_rounds - self.round, "eject": False}


if __name__ == "__main__":
    print("=== round_guard self-test ===")
    ok = True

    # Case A: never passes -> must EJECT at round 3 (max_rounds=3)
    g = RoundGuard(max_rounds=3)
    last = None
    for _ in range(5):
        last = g.record(passed=False, tokens=1200)
        if last["eject"]:
            break
    caseA = last["eject"] and last["round"] == 3 and last["tokens_total"] == 3600
    ok = ok and caseA
    print(f"  [never-pass] {'OK' if caseA else 'XX'} -> {last['action']} @r{last['round']} burn={last['tokens_total']}")

    # Case B: passes on round 2 -> ACCEPT, no eject
    g2 = RoundGuard(max_rounds=3)
    g2.record(passed=False, tokens=900)
    rB = g2.record(passed=True, tokens=800)
    caseB = (rB["action"] == "ACCEPT") and (not rB["eject"]) and rB["tokens_total"] == 1700
    ok = ok and caseB
    print(f"  [pass-r2]    {'OK' if caseB else 'XX'} -> {rB['action']} @r{rB['round']} burn={rB['tokens_total']}")

    print("RESULT:", "ALL PASS" if ok else "FAILURES")
    raise SystemExit(0 if ok else 1)
