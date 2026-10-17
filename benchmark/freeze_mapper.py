"""Freeze/verify the new semantic held-out inputs, labels and mapper source."""

import hashlib
import json
from pathlib import Path

from benchmark.semantic_held_out import held_out_cases


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark/frozen/semantic_held_out_v1.json"
SOURCES = ("core/schema_mapper.py", "core/claims.py", "benchmark/mapper_evaluation.py", "benchmark/semantic_held_out.py")


def snapshot(cases):
    return {
        "evaluation_role": "held_out", "frozen_before_first_scored_run": True,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        "cases": [{"metadata": case.metadata, "columns": list(case.inputs.data.columns),
                   "claim": case.inputs.claim, "schema_descriptions": case.inputs.descriptions,
                   "records_sha256": hashlib.sha256(case.inputs.data.to_json(orient="records").encode()).hexdigest()}
                  for case in cases],
    }


def verify_frozen(cases):
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if snapshot(cases) != expected:
        raise ValueError("Held-out inputs/labels/mapper changed after freezing. Relabel this set development and create a new held-out set before scoring.")


if __name__ == "__main__":
    if MANIFEST.exists():
        verify_frozen(held_out_cases())
        print("Existing held-out freeze verified; not overwritten.")
    else:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(snapshot(held_out_cases()), indent=2), encoding="utf-8")
        print("Held-out inputs, gold labels and source frozen before first scored run.")
