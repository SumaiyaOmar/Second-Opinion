"""Evidence chart specifications built only from existing calculated outputs."""

import math


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _chart(title, rows, unit="metric value"):
    if not rows or any(not _finite(row.get("value")) for row in rows):
        return None
    return {
        "title": title, "data": {"values": rows},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "category", "type": "nominal", "sort": None, "title": None},
            "xOffset": {"field": "series", "sort": None},
            "y": {"field": "value", "type": "quantitative", "title": unit,
                  "scale": {"zero": True, **({"domain": [0, 1]} if unit == "row share" else {})},
                  **({"axis": {"format": ".0%"}} if unit == "row share" else {})},
            "color": {"field": "series", "type": "nominal", "sort": None,
                      "scale": {"range": ["#476581", "#d07b38"]}, "title": None},
            "tooltip": [{"field": "category"}, {"field": "series"}, {"field": "value", "type": "quantitative"}],
        },
        "height": 260,
    }


def _labels(audit):
    comparison = audit.get("comparison") or {}
    return {"right": f"Baseline: {comparison.get('right', 'right')}",
            "left": f"Comparison: {comparison.get('left', 'left')}"}


def aggregate_chart(audit):
    if not isinstance(audit, dict):
        return None
    values = audit.get("computed_values") or {}
    if not all(_finite(values.get(side)) for side in ("right", "left")):
        return None
    labels = _labels(audit)
    return _chart("Aggregate baseline vs comparison", [
        {"category": str(audit.get("metric") or "Metric"), "series": labels[side], "value": values[side]}
        for side in ("right", "left")
    ])


def segment_chart(investigation, audit):
    if not isinstance(investigation, dict) or investigation.get("finding") == "inconclusive":
        return None
    labels = _labels(audit or {})
    rows = investigation.get("segment_results") or []
    if any(not isinstance(row, dict) or "segment" not in row for row in rows):
        return None
    return _chart("Segment baseline vs comparison", [
        {"category": str(row["segment"]), "series": labels[side], "value": row.get(side)}
        for row in rows for side in ("right", "left")
    ])


def mix_chart(investigation, audit):
    if not isinstance(investigation, dict) or investigation.get("finding") == "inconclusive":
        return None
    labels = _labels(audit or {})
    rows = investigation.get("segment_weights") or []
    if any(not isinstance(row, dict) or "segment" not in row for row in rows):
        return None
    if any(not _finite(row.get(f"{side}_share")) or not 0 <= row[f"{side}_share"] <= 1 for row in rows for side in ("right", "left")):
        return None
    return _chart("Segment composition", [
        {"category": str(row["segment"]), "series": labels[side], "value": row.get(f"{side}_share")}
        for row in rows for side in ("right", "left")
    ], "row share")


def stress_chart(critic, name, audit):
    if not isinstance(critic, dict):
        return None
    checks = critic.get("checks_run") or []
    check = next((check for check in checks if isinstance(check, dict) and check.get("name") == name), None)
    if not check or check.get("status") == "not_applicable":
        return None
    original, stress = check.get("original_result"), check.get("stress_result")
    if not isinstance(original, dict) or not isinstance(stress, dict):
        return None
    labels = _labels(audit or {})
    labels["overall"] = "Overall"
    first = original.get("computed_values") or {}
    second = stress.get("computed_values") or {}
    sides = ["right", "left"] if "left" in first else ["overall"]
    if name == "mean_vs_median":
        title, series = "Mean vs median", ("Mean", "Median")
    elif name == "outlier_removal":
        title, series = "Original vs outlier-removed", ("Original", "Outlier-removed")
    else:
        return None
    return _chart(title, [
        {"category": labels[side], "series": label, "value": values.get(side)}
        for side in sides for label, values in zip(series, (first, second))
    ])


def evidence_charts(audit=None, investigation=None, critic=None):
    """None means unavailable, never a fabricated zero. No raw dataset/model input."""
    return {
        "aggregate": aggregate_chart(audit),
        "segments": segment_chart(investigation, audit),
        "composition": mix_chart(investigation, audit),
        "mean_vs_median": stress_chart(critic, "mean_vs_median", audit),
        "outlier_removal": stress_chart(critic, "outlier_removal", audit),
    }
