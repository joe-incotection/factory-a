# Gate C Runner Batch Mode (v4)

Adds:
- --batch mode to run multiple module zips (supports globs like *.zip)
- --out to write summary CSV
- run() now returns a result dict used for batch summaries
- Stage 6 replay + write-once preserved

Example:
  python gate_c_runner.py *.zip --batch --out summary.csv

## Hotfix v4.1
- Added missing typing import: List (and ensured Any/Dict/Optional present).

## Hotfix v4.2
- Added missing imports: argparse, csv.

## Hotfix v4.3
- Batch mode now uses a fresh GateCRunner per module to prevent Python import/path contamination between modules.
- Each runner now uses a unique work_dir under the temp folder (run_<id>) to avoid cross-run collisions.
