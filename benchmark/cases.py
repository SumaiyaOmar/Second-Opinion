"""Frozen development/held-out generators and a local documented-case interface."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd


TYPES = ("simpson", "causal", "outlier", "window", "insufficient", "clean")
SEEDS = {"development": tuple(range(1103, 1109)), "held_out": tuple(range(8101, 8107))}


@dataclass
class AnalysisInput:
    data: pd.DataFrame
    claim: str
    mapping: dict
    segment_column: str | None


@dataclass
class BenchmarkCase:
    metadata: dict
    inputs: AnalysisInput


def generated_cases(split):
    if split not in SEEDS:
        raise ValueError("Synthetic split must be development or held_out.")
    cases = []
    for index, kind in enumerate(TYPES):
        seed = SEEDS[split][index]
        rng = np.random.default_rng(seed)
        offset = int(rng.integers(0, 5))
        rows = []
        def add(period, segment, count, value):
            rows.extend({"period": period, "segment": segment, "score": value + offset} for _ in range(count))
        mapping = dict(confirmed=True, calculation_type="two_periods", metric="score",
                       aggregation="mean", operator="greater", group_column="period",
                       left="2026-03", right="2026-02")
        claim = "Mean score increased in 2026-03 compared with 2026-02."
        segment = "segment"
        expected, error, driver, abstain = "Partially supported", kind, None, False
        if kind == "simpson":
            for args in (("2026-02", "high", 2, 90), ("2026-02", "low", 18, 30),
                         ("2026-03", "high", 18, 80), ("2026-03", "low", 2, 20)):
                add(*args)
            driver = "mix_effect"
        elif kind == "outlier":
            add("2026-02", "all", 20, 5)
            add("2026-03", "all", 19, 1)
            add("2026-03", "all", 1, 1000)
            segment, driver = None, "outlier_sensitivity"
        elif kind == "insufficient":
            add("2026-02", "all", 2, 10)
            add("2026-03", "all", 2, 20)
            segment, expected, abstain = None, "Inconclusive", True
        else:
            for period, value in (("2026-01", 0), ("2026-02", 10), ("2026-03", 20),
                                  ("2026-04", -100 if kind == "window" else 30)):
                for label in ("A", "B"):
                    add(period, label, 20, value)
            if kind == "causal":
                claim = "The policy caused mean score to increase in 2026-03 compared with 2026-02."
                expected, abstain, segment = "Inconclusive", True, None
            elif kind == "clean":
                expected, error, segment = "Supported", None, None
            else:
                driver, segment = "window_sensitivity", None
        # Order is seed-controlled; labels are fixed independently of predictions.
        data = pd.DataFrame(rows).iloc[rng.permutation(len(rows))].reset_index(drop=True)
        cases.append(BenchmarkCase({
            "case_id": f"{split}-{index + 1:03d}", "split": split, "case_type": kind,
            "expected_status": expected, "expected_error_type": error, "expected_driver": driver,
            "should_abstain": abstain, "is_clean_control": kind == "clean", "generation_seed": seed,
            "provenance": "Frozen synthetic construction; not independently sampled real-world evidence.",
        }, AnalysisInput(data, claim, mapping, segment)))
    return cases


def load_documented_cases(manifest_path):
    """Load local public-example CSVs only; never download or relabel synthetic data.

    Manifest entries contain metadata, csv_path, claim, mapping, segment_column,
    source_citation, and transcription_notes. Metadata labels are kept separate.
    """
    path = Path(manifest_path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for entry in entries:
        if not entry.get("source_citation") or not entry.get("transcription_notes"):
            raise ValueError("Documented cases require citation and transcription notes.")
        metadata = dict(entry["metadata"], split="real_documented",
                        provenance=entry["source_citation"], transcription_notes=entry["transcription_notes"])
        required = {"case_id", "case_type", "expected_status", "expected_error_type", "expected_driver",
                    "should_abstain", "is_clean_control", "generation_seed"}
        if not required <= metadata.keys():
            raise ValueError("Documented case metadata is incomplete.")
        data = pd.read_csv(path.parent / entry["csv_path"])
        if entry.get("format") == "binomial_counts":
            rows = []
            for row in data.to_dict(orient="records"):
                successes, patients = int(row["successes"]), int(row["patients"])
                if not 0 <= successes <= patients:
                    raise ValueError("Invalid binomial counts.")
                for outcome, count in ((1, successes), (0, patients - successes)):
                    rows.extend({"treatment": row["treatment"], "stone_size": row["stone_size"],
                                 "success": outcome} for _ in range(count))
            data = pd.DataFrame(rows)
            metadata["representation_note"] = "Expanded anonymous binary outcomes reproduce published count cells only; no patient covariates, order or records are reconstructed."
        cases.append(BenchmarkCase(metadata, AnalysisInput(
            data, entry["claim"], entry["mapping"], entry.get("segment_column"))))
    return cases
