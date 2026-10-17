"""Freeze final inputs/gold/source hashes. This module never runs a predictor."""

import hashlib
import json
from pathlib import Path

from benchmark.semantic_final_held_out import final_held_out_cases


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark/frozen/semantic_final_held_out_v1.json"
SOURCES = ("core/schema_mapper.py", "core/schema_mapping_validation.py", "core/claims.py",
           "benchmark/mapper_evaluation.py", "benchmark/semantic_final_held_out.py")


def snapshot(cases):
    return {
        "split": "semantic_final_held_out", "evaluation_role": "held_out", "scored_at_freeze": False,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        "cases": [{"metadata": c.metadata, "claim": c.inputs.claim, "columns": list(c.inputs.data.columns),
                   "descriptions": c.inputs.descriptions,
                   "records_sha256": hashlib.sha256(c.inputs.data.to_json(orient="records").encode()).hexdigest()}
                  for c in cases],
    }


def verify_final_frozen(cases):
    if snapshot(cases) != json.loads(MANIFEST.read_text(encoding="utf-8")):
        raise ValueError("Final held-out inputs, gold labels or mapper source changed after freezing.")


if __name__ == "__main__":
    if MANIFEST.exists():
        verify_final_frozen(final_held_out_cases())
        print("Existing final freeze verified; not overwritten. No evaluation run.")
    else:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(snapshot(final_held_out_cases()), indent=2), encoding="utf-8")
        print("Final 12-case set frozen before any scored run. No evaluation run.")
