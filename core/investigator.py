"""Deterministic Investigator orchestration; no model decides the finding."""

from dataclasses import asdict
import hashlib
import math

import pandas as pd

from core.auditor import build_audit_request
from tools.analytics import (
    audit_dataset, segment_comparison, decompose_mix_shift, detect_direction_reversal,
)


def investigate_segments(data, claim, audit_result, confirmed_mapping=None,
                         segment_column=None, segment_confirmed=False,
                         min_segment_rows=2, material_fraction=0.10):
    """Test a fixed segment/mix hypothesis against a fresh matching audit.

    A material mix effect is at least 10% of the absolute decomposition components.
    Strict full reversal takes precedence over material mix classification.
    """
    hypothesis = "Changes in segment composition may be associated with the aggregate comparison."
    result = {
        "hypothesis": hypothesis, "finding": "inconclusive", "overall_change": None,
        "segment_results": [], "segment_weights": [], "mix_shift_evidence": {},
        "strongest_supported_driver": None, "limitations": [],
        "computational_receipt": {"executed": False},
    }
    try:
        if claim.get("claim_type") != "comparison":
            raise ValueError("Investigation requires an extracted comparison claim.")
        if segment_confirmed is not True or segment_column is None:
            raise ValueError("Confirm a segment column before investigation.")
        if not isinstance(material_fraction, (int, float)) or isinstance(material_fraction, bool) or not math.isfinite(material_fraction) or not 0 < material_fraction <= 1:
            raise ValueError("Material fraction must be greater than zero and at most one.")
        request = build_audit_request(claim, data, confirmed_mapping)
        fresh_audit = audit_dataset(data, request)
        if fresh_audit != audit_result or fresh_audit["status"] == "Inconclusive":
            raise ValueError("A current completed comparison audit matching these mappings is required.")
        if request.calculation_type not in {"two_periods", "two_groups"}:
            raise ValueError("Investigation requires a two-period or two-group audit.")
        segments = segment_comparison(data, request, segment_column, min_segment_rows)
        effects = decompose_mix_shift(segments, request.aggregation)
        overall = effects["overall"]
        numeric = [overall["left"], overall["right"], overall["change"],
                   effects["within_effect"], effects["mix_effect"], effects["volume_effect"], effects["residual"]]
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("Decomposition exceeded the finite numeric range.")
        scale = max(1.0, abs(overall["left"]), abs(overall["right"]),
                    *(abs(row[side]) for row in segments for side in ("left", "right")))
        tolerance = 1e-9 * scale
        if abs(effects["residual"]) > tolerance:
            raise ValueError("Decomposition failed to reconcile with the aggregate change.")
        size = math.fsum(abs(effects[key]) for key in ("within_effect", "mix_effect", "volume_effect"))
        threshold = max(tolerance, material_fraction * size)
        reversal = detect_direction_reversal(overall["change"], segments, tolerance)
        material = abs(effects["mix_effect"]) > tolerance and abs(effects["mix_effect"]) >= threshold
        finding = "direction_reversal" if reversal else ("mix_shift" if material else "no_material_mix_effect")
        components = {key: effects[key] for key in ("within_effect", "mix_effect", "volume_effect")}
        driver = max(components, key=lambda key: abs(components[key]))
        explanation = {
            "direction_reversal": "Evidence supports an aggregate-vs-every-segment direction reversal, consistent with a composition shift.",
            "mix_shift": "Evidence supports a material arithmetic contribution associated with changing segment shares, without full direction reversal.",
            "no_material_mix_effect": "The decomposition shows no material mix effect at the configured threshold; segment effects may still differ.",
        }[finding]
        result.update({
            "finding": finding, "overall_change": overall, "segment_results": segments,
            "segment_weights": effects.pop("weights"),
            "mix_shift_evidence": {**effects, "material_threshold": threshold, "explanation": explanation},
            "strongest_supported_driver": {
                "component": driver if abs(components[driver]) > tolerance else "none",
                "contribution": components[driver],
                "description": "Largest absolute arithmetic component; observational association, not a proven cause.",
            },
            "limitations": [
                "Each row is one equally weighted observation; pre-aggregated rates need explicit denominator support and are outside this slice.",
                "Only the selected exact buckets are compared; no calendar or causal inference is made.",
                "Sum decompositions include a separate row-volume component; Simpson direction reversal uses the audited aggregation.",
                "All segments must appear with complete finite data and sufficient rows in both buckets; sample sizes are not statistical significance tests.",
                "Improvement depends on the metric's business meaning; the calculation reports numeric direction only.",
                "Materiality is a heuristic, not a significance test. Signed contributions can offset each other.",
            ],
            "computational_receipt": {
                "executed": True, "algorithm": "symmetric_segment_decomposition_v1",
                "audit_request": asdict(request), "segment_column": segment_column,
                "data_sha256": hashlib.sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest(),
                "columns": [{"name": str(column), "dtype": str(dtype)} for column, dtype in zip(data.columns, data.dtypes)],
                "input_rows": len(data), "selected_rows": sum(overall["row_counts"].values()),
                "excluded_rows": len(data) - sum(overall["row_counts"].values()),
                "minimum_rows_per_segment_per_bucket": min_segment_rows,
                "material_fraction": material_fraction, "direction_tolerance": tolerance,
                "mean_formula": "within = sum(avg_share * delta_segment_mean); mix = sum(avg_segment_mean * delta_share); delta_mean = within + mix",
                "sum_formula": "delta_sum = avg_N * within + avg_N * mix + avg_mean * delta_N (volume)",
                "reconstruction_residual": effects["residual"],
                "weight_definition": "segment row count / bucket row count",
                "left": request.left, "right": request.right,
            },
        })
    except (TypeError, ValueError, OverflowError) as exc:
        result["limitations"] = [str(exc)]
    return result
