import argparse
import sys
import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone

# ============================================================================
# 🏭 Factory-A Multi-Integrator (REAL ASSEMBLE for modules already locked in vault)
# ----------------------------------------------------------------------------
# Purpose:
#   - COLLECT: (optional) verify modules exist in vault (no simulation)
#   - ASSEMBLE: create integrated_project/project_bundle.zip by MERGING each
#               <module>_SINGLE_bundle.zip (content merge) + writing a new manifest.json
#
# This tool STOPS after bundle creation (Gate-C/Vault boundary). Final gate is run by integrate.py.
# ============================================================================
RUN_MODE = "ASSEMBLE"   # "COLLECT" or "ASSEMBLE"
_HARDCODED_MODULES = [
    "trinity_m1",
    "trinity_m2",
    "trinity_m1_adapter",
    "gim",
    "eql",
    "vapd",
    "router",
    "omnigraph_full",
    "data_collector",
    "evidence_gatekeeper",
    "vip_v1_1",
    "e2_v2",
    "e3_v2",
    "guard",
    "mt5_executor",
    "compute_runner",
    "mt5_position_manager",
    "truth_feed_manager",
    "live_runner_continuous",
    "ws1_the_pulse",
]  # fallback if project_manifest.yaml is absent or PyYAML is unavailable
ENABLE_FINAL_GATE = False  # keep False (final gate handled by integrate.py)

# G-Score threshold (LAW 8 / Policy Rule C.3): modules must achieve >= 0.99.
# NOTE: Policy document states 0.95; all tools enforce 0.99 (stricter standard agreed by S1).
# integrate_multi_m.py delegates G-Score enforcement entirely to integrate.py.
G_SCORE_THRESHOLD = 0.99

JOE_ROOT = Path(r"C:\\Factory-A")

# ── SANDBOX ISOLATION (stage_tests_V2_patch) ─────────────────────────────────
# All write-paths redirected to sandbox. Real vault/outputs/stage_tests untouched.
SANDBOX_ROOT   = Path(__file__).parent.resolve()   # C:\Factory-A\stage_tests_V2_patch
RECEIPT_VAULT  = SANDBOX_ROOT / "vault"
INTEGRATED_OUT = SANDBOX_ROOT / "integrated_project"


def _load_project_modules() -> list:
    """Load the module list from the SSOT YAML; fall back to _HARDCODED_MODULES.

    SSOT file : C:/Factory-A/project_manifest.yaml
    Schema    : { modules: [str, ...] }

    Fallback rules (non-fatal):
      - YAML file absent  → warn + use hardcoded list
      - PyYAML not installed → warn + use hardcoded list
    Hard-fail (fatal):
      - YAML file present but 'modules' key missing/wrong type → RuntimeError
      - Any module entry is not a non-empty string → RuntimeError
    """
    manifest_path = SANDBOX_ROOT / "project_manifest.yaml"
    if not manifest_path.exists():
        print("[WARN] project_manifest.yaml not found — using hardcoded module list")
        return list(_HARDCODED_MODULES)
    try:
        import yaml
    except ImportError:
        print("[WARN] PyYAML not installed — using hardcoded module list")
        return list(_HARDCODED_MODULES)
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list) or not modules:
        raise RuntimeError(
            f"PIPELINE_ABORT: project_manifest.yaml malformed — "
            f"expected non-empty 'modules' list, got: {type(modules).__name__}"
        )
    for entry in modules:
        if not isinstance(entry, str) or not entry.strip():
            raise RuntimeError(
                f"PIPELINE_ABORT: project_manifest.yaml — "
                f"all module entries must be non-empty strings, got: {entry!r}"
            )
    print(f"[OK] Loaded {len(modules)} modules from project_manifest.yaml")
    return modules


PROJECT_MODULES = _load_project_modules()


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_pytest_ini(z: zipfile.ZipFile) -> None:
    # Make root importable for pytest; keep consistent with single bundles
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


def _find_single_bundle(vault_dir: Path, module_id: str) -> Path:
    # Prefer exact: <module_id>_SINGLE_bundle.zip
    exact = vault_dir / f"{module_id}_SINGLE_bundle.zip"
    if exact.exists():
        return exact
    # Fallback glob: require exactly one match — multiple bundles are ambiguous
    # and must not be silently resolved by alphabetical order.
    matches = sorted(vault_dir.glob("*_SINGLE_bundle.zip"))
    if len(matches) > 1:
        found = ", ".join(m.name for m in matches)
        raise RuntimeError(
            f"PIPELINE_ABORT: Multiple bundles found in vault/{module_id} — "
            f"ambiguous selection; remove stale bundles and keep exactly one.\n"
            f"Found: {found}"
        )
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Single bundle not found in vault/{module_id} (expected *_SINGLE_bundle.zip)")


def run_integration_gates(bundles: list) -> None:
    """Run Integration Gates I.1–I.4 (Policy Section 10).

    Uses only existing vault YAML/JSON files. No new schema files created.

    I.1 — ABI compatibility     : each module must have a parseable GOLDEN_IO_LOCK
                                   in its vault directory.
    I.2 — Schema declaration    : GOLDEN_IO_LOCK must contain at least one schema,
                                   version, module, or law field.
    I.3 — Toolchain consistency : all module Gate C receipts must share the same
                                   toolchain_manifest_digest.
    I.4 — Reason code consistency: module-specific reason codes must not collide
                                   across modules (pipeline-level codes shared by
                                   design are excluded from collision check).

    Raises:
        RuntimeError: PIPELINE_ABORT if any gate detects an issue.
    """
    print("  🔎 Running Integration Gates I.1–I.4 (Policy Section 10)...")
    all_issues: list = []

    # --- yaml availability (I.1, I.2, I.4) ---
    try:
        import yaml as _yaml
    except ImportError:
        _yaml = None
        all_issues.append(
            "[I.1/I.2/I.4] PyYAML not installed — cannot verify ABI/schema/reason-code gates"
        )

    # ------------------------------------------------------------------
    # Gates I.1 and I.2 — per module, uses GOLDEN_IO_LOCK in vault
    # ------------------------------------------------------------------
    _SCHEMA_KEYS = frozenset({
        "input_contract", "output_contract",
        "input_schema",   "output_schema",
        "schema",         "modules",
    })
    _MINIMUM_KEYS = frozenset({"version", "module", "law"})

    if _yaml is not None:
        for module_id, _ in bundles:
            vdir = RECEIPT_VAULT / module_id
            lock_files = sorted(vdir.glob("*GOLDEN_IO_LOCK*.yaml"))

            # Gate I.1 — ABI: GOLDEN_IO_LOCK must exist and be parseable
            if not lock_files:
                all_issues.append(
                    f"[I.1] {module_id}: No GOLDEN_IO_LOCK file found in vault/{module_id}"
                )
                continue

            lock_path = lock_files[0]
            try:
                with open(lock_path, encoding="utf-8") as fh:
                    lock_data = _yaml.safe_load(fh)
            except Exception as exc:
                all_issues.append(
                    f"[I.1] {module_id}: Failed to parse {lock_path.name}: {exc}"
                )
                continue

            if not isinstance(lock_data, dict):
                all_issues.append(
                    f"[I.1] {module_id}: {lock_path.name} top level is not a mapping"
                )
                continue

            print(f"    [I.1] {module_id}: OK ({lock_path.name})")

            # Gate I.2 — Schema: contract fields must be declared
            has_schema  = bool(_SCHEMA_KEYS  & lock_data.keys())
            has_minimum = bool(_MINIMUM_KEYS & lock_data.keys())
            if not has_schema and not has_minimum:
                all_issues.append(
                    f"[I.2] {module_id}: {lock_path.name} declares no schema, "
                    f"version, module, or law fields — contract undeclared"
                )
            else:
                print(f"    [I.2] {module_id}: OK (contract declared)")

    # ------------------------------------------------------------------
    # Gate I.3 — Toolchain consistency: all modules built with same toolchain
    # Source: outputs/reports/{module_id}_final_status.json
    #         result["stage2"]["full_report"]["toolchain_manifest"]
    # Digest: SHA-256 of canonical JSON (sort_keys=True, separators=(',',':'))
    # ------------------------------------------------------------------
    import hashlib as _hashlib
    tc_digests: dict = {}
    _reports_dir = SANDBOX_ROOT / "outputs" / "reports"
    for module_id, _ in bundles:
        fs_path = _reports_dir / f"{module_id}_final_status.json"
        if not fs_path.exists():
            all_issues.append(
                f"[I.3] {module_id}: final_status.json not found: {fs_path}"
            )
            continue
        try:
            with open(fs_path, encoding="utf-8") as fh:
                fs = json.load(fh)
            obj = fs["stage2"]["full_report"]["toolchain_manifest"]
            digest = _hashlib.sha256(
                json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
            ).hexdigest()
            tc_digests[module_id] = digest
        except (KeyError, TypeError) as exc:
            all_issues.append(
                f"[I.3] {module_id}: toolchain_manifest not found in final_status.json: {exc}"
            )
        except Exception as exc:
            all_issues.append(
                f"[I.3] {module_id}: Failed to load final_status.json: {exc}"
            )

    unique_digests = set(tc_digests.values())
    if len(unique_digests) > 1:
        digest_lines = "\n".join(
            f"  {m}: {d[:16]}..." for m, d in sorted(tc_digests.items())
        )
        all_issues.append(
            f"[I.3] toolchain_manifest_digest MISMATCH — "
            f"{len(unique_digests)} distinct values found:\n{digest_lines}"
        )
    elif unique_digests:
        print(f"    [I.3] Toolchain digest consistent across {len(tc_digests)} modules")

    # ------------------------------------------------------------------
    # Gate I.4 — Reason code consistency
    # Load pipeline-level codes (REASON_CODES_v1.yaml) first; these are
    # shared by design and excluded from cross-module collision detection.
    # ------------------------------------------------------------------
    if _yaml is not None:
        _pipeline_rc_path = SANDBOX_ROOT / "gate_c" / "REASON_CODES_v1.yaml"
        pipeline_codes: set = set()
        if _pipeline_rc_path.exists():
            try:
                with open(_pipeline_rc_path, encoding="utf-8") as fh:
                    pl_data = _yaml.safe_load(fh)
                if isinstance(pl_data, dict):
                    # Codes are nested under category keys as sub-dicts
                    for cat_val in pl_data.values():
                        if isinstance(cat_val, dict):
                            pipeline_codes.update(cat_val.keys())
            except Exception:
                pass  # non-fatal; worst case all codes are checked for collisions

        code_owners: dict = {}
        for module_id, _ in bundles:
            vdir = RECEIPT_VAULT / module_id
            rc_files = sorted(set(
                list(vdir.glob("*REASON_CODES*.yaml")) +
                list(vdir.glob("*REASON_CODE*.yaml"))
            ))
            if not rc_files:
                all_issues.append(
                    f"[I.4] {module_id}: No REASON_CODES file found in vault/{module_id}"
                )
                continue

            module_codes: set = set()
            for rc_path in rc_files:
                try:
                    with open(rc_path, encoding="utf-8") as fh:
                        rc_data = _yaml.safe_load(fh)
                    if not isinstance(rc_data, dict):
                        continue
                    # Format 1: codes: [list]  (e.g. TRINITY_M1_REASON_CODES)
                    for code in rc_data.get("codes", []):
                        if isinstance(code, str) and code.strip():
                            module_codes.add(code)
                    # Format 2: allowlist: [list]  (e.g. ROUTER merged)
                    for code in rc_data.get("allowlist", []):
                        if isinstance(code, str) and code.strip():
                            module_codes.add(code)
                    # Format 3: modules.*.allowlist
                    for mod_val in rc_data.get("modules", {}).values():
                        if isinstance(mod_val, dict):
                            for code in mod_val.get("allowlist", []):
                                if isinstance(code, str) and code.strip():
                                    module_codes.add(code)
                    # Format 4: severity: {code: severity_str}  (e.g. TRINITY_M1)
                    for code in rc_data.get("severity", {}):
                        if isinstance(code, str) and code.strip():
                            module_codes.add(code)
                except Exception as exc:
                    all_issues.append(
                        f"[I.4] {module_id}: Failed to parse {rc_path.name}: {exc}"
                    )

            for code in module_codes:
                code_owners.setdefault(code, []).append(module_id)

        # Flag only module-specific collisions (exclude shared pipeline-level codes)
        collisions = {
            code: owners
            for code, owners in code_owners.items()
            if len(owners) > 1 and code not in pipeline_codes
        }
        if collisions:
            lines = "\n".join(
                f"  {code}: {sorted(owners)}"
                for code, owners in sorted(collisions.items())
            )
            all_issues.append(
                f"[I.4] Module-specific reason code collisions (same code in "
                f"multiple modules):\n{lines}"
            )
        else:
            print(
                f"    [I.4] Reason code namespace OK "
                f"({len(code_owners)} total codes, "
                f"{len(pipeline_codes)} pipeline-level excluded)"
            )

    # ------------------------------------------------------------------
    # Final gate decision
    # ------------------------------------------------------------------
    if all_issues:
        detail = "\n".join(all_issues)
        raise RuntimeError(
            f"PIPELINE_ABORT: Integration Gate failure (Policy Section 10).\n"
            f"{detail}"
        )
    print("  ✅ Integration Gates I.1–I.4 PASS")


def collect_mode() -> None:
    print("🏭 Factory-A Multi-Integrator: COLLECT (verify vault) Mode")
    print(f"📂 Root:  {JOE_ROOT}")
    print(f"📁 Vault: {RECEIPT_VAULT}")
    print(f"🎯 Target modules: {PROJECT_MODULES}")
    print("-" * 60)

    ok = True
    for module_id in PROJECT_MODULES:
        vdir = RECEIPT_VAULT / module_id
        if not vdir.exists():
            print(f"  ❌ Missing: vault/{module_id} (folder not found)")
            ok = False
            continue

        required_any = list(vdir.glob("*_SINGLE_bundle.zip"))
        if not required_any:
            print(f"  ❌ Missing: vault/{module_id}/*_SINGLE_bundle.zip")
            ok = False
            continue

        print(f"  ✅ OK: {module_id} -> {required_any[0].name}")

    print("-" * 60)
    if ok:
        print("✅ COLLECT verification PASS (ready for ASSEMBLE)")
    else:
        print("❌ COLLECT verification FAIL (fix missing vault artifacts first)")


def assemble_mode() -> Path:
    print("🏭 Factory-A Multi-Integrator: ASSEMBLE Mode (REAL merge)")
    print(f"📂 Root:  {JOE_ROOT}")
    print(f"📁 Vault: {RECEIPT_VAULT}")
    print(f"🎯 Target modules: {PROJECT_MODULES}")
    print(f"📦 Output: {INTEGRATED_OUT}")
    print("-" * 60)

    INTEGRATED_OUT.mkdir(parents=True, exist_ok=True)
    bundle_path = INTEGRATED_OUT / "project_bundle.zip"

    # Resolve bundles first (fail-fast)
    bundles: list[tuple[str, Path]] = []
    for module_id in PROJECT_MODULES:
        vdir = RECEIPT_VAULT / module_id
        if not vdir.exists():
            raise FileNotFoundError(f"Vault folder not found: {vdir}")
        b = _find_single_bundle(vdir, module_id)
        bundles.append((module_id, b))
        print(f"  📦 Using {module_id}: {b.name}")

    # Integration Gates I.1–I.4 (Policy Section 10) — run before merge
    run_integration_gates(bundles)

    # Merge zip contents
    seen_paths: set[str] = set()
    merged_modules = []
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as out_zip:
        # Write root pytest.ini (override)
        _write_pytest_ini(out_zip)
        seen_paths.add("pytest.ini")

        # Merge each single bundle (skip their manifest/pytest.ini; keep everything else)
        for module_id, bpath in bundles:
            merged_modules.append(module_id)
            with zipfile.ZipFile(bpath, "r") as in_zip:
                for info in in_zip.infolist():
                    name = info.filename

                    # Normalize directory entries
                    if name.endswith("/"):
                        continue

                    # Skip per-bundle manifest/pytest.ini (we write global ones)
                    if name in {"manifest.json", "pytest.ini"}:
                        continue

                    # Avoid collisions deterministically: fail if collision with different content
                    if name in seen_paths:
                        raise RuntimeError(f"Path collision while merging bundles: {name}")

                    data = in_zip.read(name)
                    out_zip.writestr(name, data)
                    seen_paths.add(name)

        # Write integrated manifest.json
        manifest = {
            "module_inventory": [{"module_id": m, "version": "1.0"} for m in merged_modules],
            "graph": {"nodes": merged_modules, "edges": [], "required_nodes": merged_modules},
            "integrator": {
                "tool": "integrate_multi_m.py (ASSEMBLE REAL merge)",
                "timestamp": _utc_now_z(),
            },
        }
        out_zip.writestr("manifest.json", json.dumps(manifest, indent=2))
        # Overwrite allowed (manifest not previously added)
        print("  ✅ manifest.json written")

    print("-" * 60)
    print(f"✅ Bundle created: {bundle_path}")
    print(f"📦 Size: {bundle_path.stat().st_size:,} bytes")
    print("⏸️ ASSEMBLE Complete - Ready for integrate.py (Final Gate)")
    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Factory-A Multi-Integrator: assemble or verify vault modules."
    )
    parser.add_argument(
        "--mode",
        choices=["COLLECT", "ASSEMBLE"],
        default=None,
        help=(
            "Run mode: COLLECT (verify vault) or ASSEMBLE (merge bundles). "
            f"Defaults to module-level RUN_MODE = '{RUN_MODE}'."
        ),
    )
    args = parser.parse_args()

    # CLI --mode takes precedence; fall back to module-level RUN_MODE constant.
    effective_mode = (args.mode or RUN_MODE).upper()

    if effective_mode == "COLLECT":
        collect_mode()
        return

    if effective_mode != "ASSEMBLE":
        print(f"❌ Invalid mode: {effective_mode!r} (use 'COLLECT' or 'ASSEMBLE')")
        sys.exit(1)

    try:
        bundle_path = assemble_mode()
    except Exception as e:
        print(f"❌ ASSEMBLE failed: {e}")
        raise

    if ENABLE_FINAL_GATE:
        # Intentionally disabled by default; final gate should run via integrate.py
        print("⚠️ ENABLE_FINAL_GATE=True is not recommended. Use integrate.py instead.")
        print(f"   Bundle ready at: {bundle_path}")


if __name__ == "__main__":
    main()

