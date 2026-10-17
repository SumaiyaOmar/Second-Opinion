"""Deterministic dataset profiling; no model calls."""

import pandas as pd
import math


def inconclusive_result(metric, reason, calculation_type=None):
    return {
        "status": "Inconclusive",
        "calculation_type": calculation_type,
        "metric": metric,
        "comparison": None,
        "computed_values": {},
        "difference": None,
        "evidence_summary": "No conclusion can be drawn from this calculation.",
        "limitations": [reason],
        "calculation": None,
    }


def audit_dataset(data: pd.DataFrame, request) -> dict:
    """Compute a confirmed sum/mean overall or across two explicit value buckets.

    For comparisons, left is the subject/current bucket and right is the baseline.
    No dates are inferred, no numeric strings coerced, and no model is involved.
    """
    def fail(reason):
        return inconclusive_result(request.metric, reason, request.calculation_type)

    if request.calculation_type not in {"overall", "two_periods", "two_groups"}:
        return fail("Unsupported calculation type.")
    if request.aggregation not in {"sum", "mean"} or request.operator not in {"greater", "less", "equal"}:
        return fail("Confirm a supported aggregation and comparison operator.")
    if request.metric not in data.columns or list(data.columns).count(request.metric) != 1:
        return fail("Metric column is missing or ambiguous; confirm the mapping.")
    if not pd.api.types.is_numeric_dtype(data[request.metric]) or pd.api.types.is_bool_dtype(data[request.metric]):
        return fail("Metric must be a numeric column; values are not silently converted.")
    if request.target_kind not in {"absolute", "percent"}:
        return fail("Target kind must be absolute or percent.")
    if request.target is not None and (isinstance(request.target, bool) or not isinstance(request.target, (int, float)) or not math.isfinite(request.target)):
        return fail("Target must be a finite number.")

    limitations = [
        "Uses the user-confirmed interpretation of the claim and the uploaded rows only.",
        "Calculations use Python floating-point arithmetic.",
        "Equality uses relative and absolute tolerances of 1e-9; no rounding or unit conversion is inferred.",
    ]
    if request.calculation_type == "overall":
        if request.target is None or request.target_kind != "absolute":
            return fail("An overall claim requires an explicit absolute target.")
        if request.group_column is not None or request.left is not None or request.right is not None:
            return fail("Overall calculations do not accept bucket filters.")
        buckets = {"overall": data}
    else:
        column = request.group_column
        if column not in data.columns or list(data.columns).count(column) != 1:
            return fail("Time/segment column is missing or ambiguous; confirm the mapping.")
        if request.left is None or request.right is None or request.left == request.right:
            return fail("Select two distinct explicit period/group values.")
        labels = data[column].astype("string")
        buckets = {
            "left": data.loc[labels.eq(request.left).fillna(False)],
            "right": data.loc[labels.eq(request.right).fillna(False)],
        }
        limitations.append("Only the selected exact bucket values are compared; no calendar boundaries or period completeness are inferred.")
        if labels.isna().any():
            limitations.append(f"{int(labels.isna().sum())} rows have no bucket label and were excluded.")

    values = {}
    missing = 0
    counts = {}
    for name, bucket in buckets.items():
        series = bucket[request.metric]
        if bucket.empty or series.notna().sum() == 0:
            return fail(f"No numeric observations for {name}.")
        if not all(math.isfinite(float(value)) for value in series.dropna()):
            return fail("Metric contains non-finite values.")
        missing += int(series.isna().sum())
        try:
            total = math.fsum(float(item) for item in series.dropna())
            value = total if request.aggregation == "sum" else total / int(series.notna().sum())
        except (OverflowError, ValueError):
            return fail("Aggregation exceeded the supported finite numeric range.")
        if not math.isfinite(value):
            return fail("Aggregation produced a non-finite value.")
        values[name] = value
        counts[name] = {"rows": len(bucket), "non_missing": int(series.notna().sum())}

    if request.calculation_type == "overall":
        difference = values["overall"] - request.target
        observed, expected = values["overall"], request.target
        comparison = {"operator": request.operator, "target": request.target}
        calculation = f"{request.aggregation}({request.metric}) compared with {request.target}"
        direction_ok = None
    else:
        difference = values["left"] - values["right"]
        direction_ok = _compare(values["left"], values["right"], request.operator)
        percent = None if values["right"] == 0 else difference / abs(values["right"]) * 100
        if request.target_kind == "percent" and percent is None:
            return fail("Percentage change is undefined with a zero baseline.")
        observed = percent if request.target_kind == "percent" else difference
        expected = request.target
        comparison = {
            "column": request.group_column, "left": request.left, "right": request.right,
            "operator": request.operator, "target": request.target, "target_kind": request.target_kind,
            "percent_change": percent,
        }
        calculation = (
            f"left = {request.aggregation}({request.metric} where {request.group_column} = {request.left!r}); "
            f"right = {request.aggregation}({request.metric} where {request.group_column} = {request.right!r}); "
            "difference = left - right; percent_change = difference / abs(right) * 100 (unless right = 0)"
        )
    if not math.isfinite(difference) or (observed is not None and not math.isfinite(observed)):
        return fail("Difference produced a non-finite value.")
    if request.calculation_type == "overall":
        supported = _compare(observed, expected, request.operator)
        status = "Supported" if supported else "Unsupported"
    elif expected is None:
        status = "Supported" if direction_ok else "Unsupported"
    else:
        magnitude_ok = math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-9)
        status = "Supported" if direction_ok and magnitude_ok else (
            "Partially supported" if direction_ok else "Unsupported"
        )
    if missing:
        limitations.append(f"Excluded {missing} missing metric values from the selected rows.")
        status = "Partially supported" if status in {"Supported", "Partially supported"} else "Inconclusive"
    values["observation_counts"] = counts
    return {
        "status": status, "calculation_type": request.calculation_type,
        "metric": request.metric, "comparison": comparison,
        "computed_values": values, "difference": difference,
        "evidence_summary": f"{status}: {values}. Difference = {difference}. Based on the confirmed assertion.",
        "limitations": limitations, "calculation": calculation,
    }


def _compare(left, right, operator):
    equal = math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    return equal if operator == "equal" else (not equal and (left > right if operator == "greater" else left < right))


def profile_dataset(data: pd.DataFrame) -> dict:
    """Return dataset dimensions and a per-column profile."""
    return {
        "row_count": len(data),
        "column_count": len(data.columns),
        "columns": pd.DataFrame({
            "column": list(data.columns),
            "dtype": [str(dtype) for dtype in data.dtypes],
            "missing_values": data.isna().sum().to_list(),
        }),
    }


def segment_comparison(data, request, segment_column, min_segment_rows=2):
    """Compare all observed segments on identical, complete two-bucket rows.

    Reject incomplete/unmatched/small segments rather than silently changing the
    population. Each row is an equally weighted observation, not an aggregate cell.
    """
    columns = [request.metric, request.group_column, segment_column]
    if len(set(columns)) != 3 or any(
        column not in data.columns or list(data.columns).count(column) != 1
        for column in columns
    ):
        raise ValueError("Confirm three distinct, unambiguous metric, comparison, and segment columns.")
    if request.calculation_type not in {"two_periods", "two_groups"}:
        raise ValueError("Investigation requires an audited two-bucket comparison.")
    if request.aggregation not in {"sum", "mean"}:
        raise ValueError("Only sum and mean comparisons are supported.")
    if request.left is None or request.right is None or request.left == request.right:
        raise ValueError("Confirm two distinct comparison values.")
    if not isinstance(min_segment_rows, int) or isinstance(min_segment_rows, bool) or min_segment_rows < 1:
        raise ValueError("Minimum segment rows must be a positive integer.")
    series = data[request.metric]
    if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        raise ValueError("Metric must be numeric; no conversion is inferred.")
    labels = data[request.group_column].astype("string")
    selected = data.loc[labels.isin([request.left, request.right]), columns].copy()
    if selected.empty or selected.isna().any().any():
        raise ValueError("Selected comparison rows must have complete metric and segment values.")
    if not all(math.isfinite(float(value)) for value in selected[request.metric]):
        raise ValueError("Selected metric values must be finite.")
    selected[request.group_column] = selected[request.group_column].astype("string")
    selected[segment_column] = selected[segment_column].astype("string")
    segments = sorted(selected[segment_column].unique().tolist())
    if len(segments) < 2:
        raise ValueError("At least two meaningful segments are required.")
    results = []
    for segment in segments:
        row = {"segment": segment}
        for side, label in (("left", request.left), ("right", request.right)):
            values = selected.loc[
                selected[request.group_column].eq(label) & selected[segment_column].eq(segment),
                request.metric,
            ]
            if len(values) < min_segment_rows:
                raise ValueError(
                    f"Segment {segment!r} needs at least {min_segment_rows} rows in each bucket; "
                    "new/disappearing or small segments are not dropped."
                )
            total = math.fsum(float(value) for value in values)
            row[f"{side}_count"] = len(values)
            row[f"{side}_sum"] = total
            row[f"{side}_mean"] = total / len(values)
            row[side] = row[f"{side}_{request.aggregation}"]
        row["change"] = row["left"] - row["right"]
        row["mean_change"] = row["left_mean"] - row["right_mean"]
        results.append(row)
    return results


def segment_weights(segment_results):
    """Observation shares within each bucket, summing to one per bucket."""
    totals = {side: sum(row[f"{side}_count"] for row in segment_results) for side in ("left", "right")}
    return [
        {"segment": row["segment"],
         "left_share": row["left_count"] / totals["left"],
         "right_share": row["right_count"] / totals["right"]}
        for row in segment_results
    ]


def decompose_mix_shift(segment_results, aggregation):
    """Exact symmetric two-factor mean decomposition; sums also include volume.

    Delta mean = sum(avg share * delta segment mean)
               + sum(avg segment mean * delta share).
    Delta sum = avg N * delta mean + avg mean * delta N.
    This is an arithmetic association, not a causal attribution.
    """
    weights = segment_weights(segment_results)
    counts = {side: sum(row[f"{side}_count"] for row in segment_results) for side in ("left", "right")}
    means = {side: math.fsum(row[f"{side}_sum"] for row in segment_results) / counts[side] for side in counts}
    avg_count = (counts["left"] + counts["right"]) / 2
    scale = avg_count if aggregation == "sum" else 1.0
    contributions = []
    for row, weight in zip(segment_results, weights):
        within = (weight["left_share"] + weight["right_share"]) / 2 * row["mean_change"]
        mix = (row["left_mean"] + row["right_mean"]) / 2 * (weight["left_share"] - weight["right_share"])
        contributions.append({"segment": row["segment"], "within": within * scale, "mix": mix * scale})
    within = math.fsum(row["within"] for row in contributions)
    mix = math.fsum(row["mix"] for row in contributions)
    volume = (means["left"] + means["right"]) / 2 * (counts["left"] - counts["right"]) if aggregation == "sum" else 0.0
    overall = {
        side: math.fsum(row[f"{side}_sum"] for row in segment_results) if aggregation == "sum" else means[side]
        for side in counts
    }
    change = overall["left"] - overall["right"]
    reconstructed = math.fsum([within, mix, volume])
    return {
        "overall": {**overall, "change": change, "aggregation": aggregation, "row_counts": counts},
        "within_effect": within, "mix_effect": mix, "volume_effect": volume,
        "reconstructed_change": reconstructed, "residual": change - reconstructed,
        "segment_contributions": contributions, "weights": weights,
    }


def detect_direction_reversal(overall_change, segment_results, tolerance):
    """Strict reversal: every meaningful segment moves opposite the aggregate."""
    def sign(value):
        return 0 if abs(value) <= tolerance else (1 if value > 0 else -1)
    overall_sign = sign(overall_change)
    return bool(overall_sign and all(sign(row["change"]) == -overall_sign for row in segment_results))
