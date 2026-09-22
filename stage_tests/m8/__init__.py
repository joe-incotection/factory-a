"""M8_v2 Package - Integration & Replay Gate"""

from .m8_1_graph_validator import validate_graph, m8_1_validate_graph
from .m8_2 import m8_2_run_invariants
from .m8_3_canonicalization import canonical_json, compute_determinism_key
from .m8_4 import m8_4_replay_verify, compute_determinism_key as m4_compute_key
from .m8_5_verdict import m8_5_final_verdict

__version__ = "2.0"

__all__ = [
    "validate_graph",
    "m8_1_validate_graph",
    "m8_2_run_invariants",
    "canonical_json",
    "compute_determinism_key",
    "m8_4_replay_verify",
    "m8_5_final_verdict",
]
