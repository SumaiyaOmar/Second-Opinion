"""Fixed deterministic sensitivity checks, never a numerical confidence score."""

from dataclasses import asdict
import hashlib
import math
import re

import numpy as np
import pandas as pd

from core.auditor import build_audit_request
from core.investigator import investigate_segments
from tools.analytics import audit_dataset


CHECKS = ("alternative_window", "leave_one_segment_out", "outlier_removal", "mean_vs_median", "bootstrap")
RULES = {
    "version": "critic_v1", "iqr_multiplier": 1.5, "minimum_stressed_rows_per_bucket": 2,
    "median_material_change_fraction": 0.5, "bootstrap_minimum_rows_per_bucket": 20,
    "bootstrap_resamples": 1000, "bootstrap_seed": 20261016,
    "bootstrap_percentiles": [2.5, 97.5],
    "alternative_window": "ISO YYYY-MM or YYYY-MM-DD labels only; adjacent original bins; expand earlier bin by one predecessor and later bin by one successor; require both and no overlap.",
}


def _buckets(data, request):
    if request.calculation_type == "overall":
        return {"overall": data}
    labels = data[request.group_column].astype("string")
    return {side: data.loc[labels.eq(label).fillna(False)]
            for side, label in (("left", request.left), ("right", request.right))}


def _value(values, aggregation):
    if aggregation == "median":
        return float(np.median(values))
    total = math.fsum(float(value) for value in values)
    return total / len(values) if aggregation == "mean" else total


def _evaluate(data, request, aggregation=None):
    aggregation = aggregation or request.aggregation
    buckets = _buckets(data, request)
    values = {}
    for side, bucket in buckets.items():
        series = bucket[request.metric]
        if len(series) < 2 or series.isna().any() or not all(math.isfinite(float(x)) for x in series):
            raise ValueError("Every evaluated bucket needs at least two complete finite observations.")
        values[side] = _value(series.to_numpy(dtype=float), aggregation)
    delta = values["overall"] - request.target if "overall" in values else values["left"] - values["right"]
    if not math.isfinite(delta):
        raise ValueError("Non-finite result.")
    tolerance = max(1.0, *(abs(value) for value in values.values()), abs(request.target or 0)) * 1e-9
    direction = 0 if abs(delta) <= tolerance else (1 if delta > 0 else -1)
    holds = {"greater": direction > 0, "less": direction < 0, "equal": direction == 0}[request.operator]
    if "overall" not in values and request.target is not None:
        observed = delta
        if request.target_kind == "percent":
            if values["right"] == 0:
                raise ValueError("Percentage change is undefined with a zero baseline.")
            observed = delta / abs(values["right"]) * 100
        holds = holds and math.isclose(observed, request.target, rel_tol=1e-9, abs_tol=1e-9)
    return {"aggregation": aggregation, "computed_values": values, "difference": delta,
            "direction": direction, "assertion_holds": holds, "tolerance": tolerance,
            "row_counts": {side: len(bucket) for side, bucket in buckets.items()}}


def run_critic(data, claim, audit_result, confirmed_mapping=None, segment_column=None,
               segment_confirmed=False, investigation_result=None):
    """Run the frozen battery against a fresh audit and, if supplied, investigation.

    Held means stable to this perturbation, not proof that the assertion is true.
    Bootstrap is an IID-row percentile interval, not a calibrated reliability score.
    """
    checks = []
    original = None
    base_receipt = {"rules": RULES.copy()}

    def record(name, status, stress, interpretation, receipt=None):
        checks.append({"name": name, "status": status, "original_result": original,
                       "stress_result": stress, "interpretation": interpretation,
                       "receipt": receipt or {}})

    try:
        request = build_audit_request(claim, data, confirmed_mapping)
        fresh = audit_dataset(data, request)
        if fresh != audit_result or fresh["status"] == "Inconclusive":
            raise ValueError("A current completed audit matching the confirmed mappings is required.")
        original = _evaluate(data, request)
        segment_valid = (segment_confirmed is True and segment_column in data.columns
                         and list(data.columns).count(segment_column) == 1
                         and segment_column not in {request.metric, request.group_column})
        investigation_active = investigation_result is not None and investigation_result.get("finding") != "inconclusive"
        if investigation_active:
            fresh_investigation = investigate_segments(data, claim, fresh, confirmed_mapping,
                                                       segment_column, segment_confirmed)
            if fresh_investigation != investigation_result:
                raise ValueError("Investigation is stale or uses different mappings/thresholds.")
            original["investigation_finding"] = investigation_result["finding"]
        base_receipt.update({
            "audit_request": asdict(request), "segment_column": segment_column if segment_valid else None,
            "data_sha256": hashlib.sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest(),
            "schema": [{"column": str(c), "dtype": str(t)} for c, t in zip(data.columns, data.dtypes)],
        })

        def judge(stressed, variant=None, median=False):
            changed = (stressed["direction"] != original["direction"] or
                       stressed["assertion_holds"] != original["assertion_holds"])
            if median:
                change = abs(stressed["difference"] - original["difference"])
                threshold = max(original["tolerance"], 0.5 * abs(original["difference"]))
                stressed["material_difference_threshold"] = threshold
                changed = changed or change > threshold
            if investigation_active:
                if median:
                    stressed["investigation_finding"] = "inconclusive: median decomposition is not supported"
                    return "failed" if changed else "inconclusive"
                inv_audit = audit_dataset(variant, request)
                inv = investigate_segments(variant, claim, inv_audit, confirmed_mapping,
                                           segment_column, segment_confirmed)
                stressed["investigation_finding"] = inv["finding"]
                if inv["finding"] == "inconclusive":
                    return "failed" if changed else "inconclusive"
                changed = changed or inv["finding"] != original["investigation_finding"]
            return "failed" if changed else "held"

        # Window selection is fixed before looking at metric values.
        name = "alternative_window"
        if request.calculation_type != "two_periods":
            record(name, "not_applicable", None, "Requires a confirmed time-period comparison.")
        else:
            labels = sorted(data[request.group_column].dropna().astype(str).unique())
            if not labels or not all(re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", label) for label in labels) or len({len(label) for label in labels}) != 1:
                record(name, "not_applicable", None, "Time labels must use one ISO month/day format; no dates are guessed.")
            else:
                try:
                    pd.to_datetime(labels, errors="raise")
                    indexes = sorted([labels.index(request.left), labels.index(request.right)])
                    lo, hi = indexes
                    if hi != lo + 1 or lo == 0 or hi == len(labels) - 1:
                        raise ValueError("Need adjacent original bins and one outer neighbor on each side.")
                    earlier = labels[lo - 1:lo + 1]
                    later = labels[hi:hi + 2]
                    left_labels, right_labels = (later, earlier) if request.left > request.right else (earlier, later)
                    variant = data.copy()
                    variant[request.group_column] = variant[request.group_column].astype("string")
                    source = data[request.group_column].astype("string")
                    variant.loc[source.isin(left_labels), request.group_column] = request.left
                    variant.loc[source.isin(right_labels), request.group_column] = request.right
                    stressed = _evaluate(variant, request)
                    record(name, judge(stressed, variant), stressed, "Fixed outward expansion of both original time bins.",
                           {"left_bins": left_labels, "right_bins": right_labels, "rule": RULES["alternative_window"]})
                except (ValueError, OverflowError) as exc:
                    record(name, "inconclusive", None, str(exc))

        name = "leave_one_segment_out"
        selected = pd.concat(list(_buckets(data, request).values()))
        if not segment_valid:
            record(name, "not_applicable", None, "Requires a separately confirmed segment column.")
        elif selected[segment_column].isna().any() or selected[segment_column].nunique() < 2:
            record(name, "inconclusive", None, "Need at least two complete segment labels.")
        else:
            trials = []
            for segment in sorted(selected[segment_column].astype(str).unique()):
                variant = data.loc[data[segment_column].astype("string").ne(segment).fillna(True)]
                try:
                    stressed = _evaluate(variant, request)
                    status = judge(stressed, variant)
                    trials.append({"removed_segment": segment, "status": status, "result": stressed})
                except (ValueError, OverflowError) as exc:
                    trials.append({"removed_segment": segment, "status": "inconclusive", "reason": str(exc)})
            status = "failed" if any(t["status"] == "failed" for t in trials) else (
                "inconclusive" if any(t["status"] == "inconclusive" for t in trials) else "held")
            record(name, status, trials, "Every observed segment is removed once; no failed or ineligible trial is discarded.",
                   {"trial_count": len(trials), "minimum_remaining_rows_per_bucket": 2})

        name = "outlier_removal"
        try:
            # Pooled original buckets, fixed linear quartiles; no outcome tuning.
            values = selected[request.metric].to_numpy(dtype=float)
            if len(values) < 4:
                raise ValueError("Need at least four pooled observations for IQR filtering.")
            q1, q3 = np.quantile(values, [0.25, 0.75], method="linear")
            lower, upper = float(q1 - 1.5 * (q3 - q1)), float(q3 + 1.5 * (q3 - q1))
            variant = data.loc[data[request.metric].between(lower, upper)]
            stressed = _evaluate(variant, request)
            record(name, judge(stressed, variant), stressed, "Recomputed after pooled 1.5-IQR filtering; boundary values retained, including when IQR is zero.",
                   {"q1": float(q1), "q3": float(q3), "lower": lower, "upper": upper,
                    "removed_selected_rows": len(selected) - sum(stressed["row_counts"].values())})
        except (ValueError, OverflowError) as exc:
            record(name, "inconclusive", None, str(exc))

        name = "mean_vs_median"
        if request.aggregation != "mean":
            record(name, "not_applicable", None, "Median sensitivity applies only to mean audits.")
        else:
            try:
                stressed = _evaluate(data, request, "median")
                record(name, judge(stressed, median=True), stressed,
                       "Failed if direction/assertion changes or the delta changes by more than 50% of the original absolute delta (above numerical tolerance).",
                       {"material_change_fraction": 0.5})
            except (ValueError, OverflowError) as exc:
                record(name, "inconclusive", None, str(exc))

        name = "bootstrap"
        arrays = {side: bucket[request.metric].to_numpy(dtype=float) for side, bucket in _buckets(data, request).items()}
        receipt = {"seed": 20261016, "resamples": 1000, "percentiles": [2.5, 97.5],
                   "minimum_rows_per_bucket": 20, "scheme": "Independent IID resampling within each original bucket, original bucket sizes preserved."}
        if any(len(values) < 20 for values in arrays.values()):
            record(name, "inconclusive", None, "At least 20 complete observations per bucket are required.", receipt)
        else:
            rng = np.random.default_rng(20261016)
            deltas = []
            for _ in range(1000):
                sampled = {side: _value(rng.choice(values, len(values), replace=True), request.aggregation)
                           for side, values in arrays.items()}
                delta = sampled["overall"] - request.target if "overall" in sampled else sampled["left"] - sampled["right"]
                deltas.append(delta)
            low, high = (float(x) for x in np.quantile(deltas, [0.025, 0.975], method="linear"))
            tol = original["tolerance"]
            sign = original["direction"]
            held = (sign > 0 and low > tol) or (sign < 0 and high < -tol) or (sign == 0 and low >= -tol and high <= tol)
            failed = (sign > 0 and high < -tol) or (sign < 0 and low > tol) or (sign == 0 and (low > tol or high < -tol))
            status = "held" if held else ("failed" if failed else "inconclusive")
            if investigation_active or (request.target is not None and request.calculation_type != "overall"):
                status = "failed" if failed else "inconclusive"
            record(name, status, {"difference_interval": [low, high], "original_direction": sign},
                   "IID percentile interval for the numeric delta; does not validate investigation findings or exact comparison magnitudes. An interval spanning zero is inconclusive.", receipt)
    except (TypeError, ValueError, OverflowError) as exc:
        # No partial battery can silently masquerade as a completed successful run.
        existing = {check["name"] for check in checks}
        for name in CHECKS:
            if name not in existing:
                record(name, "inconclusive", None, str(exc))

    passed = sum(check["status"] == "held" for check in checks)
    failed = sum(check["status"] == "failed" for check in checks)
    inconclusive = sum(check["status"] == "inconclusive" for check in checks)
    applicable = passed + failed + inconclusive
    return {
        "question": "What would make this conclusion wrong?", "checks_run": checks,
        "checks_passed": passed, "checks_failed": failed, "checks_inconclusive": inconclusive,
        "stability_summary": f"Held {passed} of {applicable} applicable checks; {failed} failed; {inconclusive} inconclusive. Stability does not establish truth.",
        "failed_checks": [check for check in checks if check["status"] == "failed"],
        "limitations": [
            "Fixed sensitivity checks describe stability, not causation or a confidence score.",
            "Bootstrap assumes independent equally weighted rows; repeated entities, clustering, and time dependence require other methods.",
            "Window expansion uses neighboring observed ISO bins, not inferred calendar completeness; other time formats are not guessed.",
            "Removing outliers or segments changes the population and can change totals mechanically.",
            "Median and bootstrap cannot confirm the mean-based Investigator finding; those checks remain inconclusive unless an audit sensitivity already fails.",
            "Missing selected metric values make the battery inconclusive rather than silently changing the audited population.",
        ],
        "computational_receipts": {**base_receipt, "checks": {check["name"]: check["receipt"] for check in checks}},
    }
