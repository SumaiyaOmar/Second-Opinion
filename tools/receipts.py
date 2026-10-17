"""Normalize existing evidence into a reusable, explicit computational receipt."""

import copy


def computational_receipt(name, result, mapping=None, context=None, dataset_fingerprint=None):
    result = result or {}
    context = context or {}
    raw = result.get("computational_receipt") or result.get("receipt") or result.get("computational_receipts") or {}
    parent = context.get("computational_receipts") or context.get("computational_receipt") or {}
    upstream_fingerprint = raw.get("data_sha256") or parent.get("data_sha256")
    request = mapping or raw.get("audit_request") or parent.get("audit_request") or {}
    original = result.get("original_result") or {}
    stressed = result.get("stress_result")
    columns = [request.get(key) for key in ("metric", "group_column")]
    columns.append(raw.get("segment_column") or parent.get("segment_column"))
    counts = (result.get("computed_values") or {}).get("observation_counts")
    if counts is None:
        counts = (result.get("overall_change") or {}).get("row_counts") or original.get("row_counts")
    verdict_inputs = raw.get("inputs") or {}
    if verdict_inputs:
        inv = verdict_inputs.get("investigation") or {}
        inv_receipt = inv.get("computational_receipt") or {}
        critic_receipt = (verdict_inputs.get("critic") or {}).get("computational_receipts") or {}
        request = critic_receipt.get("audit_request") or inv_receipt.get("audit_request") or request
        columns = [request.get("metric"), request.get("group_column"), inv_receipt.get("segment_column")]
        counts = ((verdict_inputs.get("audit") or {}).get("computed_values") or {}).get("observation_counts")
        upstream_fingerprint = inv_receipt.get("data_sha256") or critic_receipt.get("data_sha256") or upstream_fingerprint
    rule = result.get("calculation") or raw.get("sum_formula" if request.get("aggregation") == "sum" else "mean_formula") or raw.get("rule")
    if not rule and name == "verdict":
        rule = {"version": raw.get("rules_version"), "decision_rule": raw.get("decision_rule")}
    if not rule:
        rule = {"check": name, "rules": parent.get("rules"), "parameters": raw}
    return copy.deepcopy({
        "name": name,
        "columns_used": list(dict.fromkeys(column for column in columns if column is not None)),
        "confirmed_mapping": request,
        "filters_or_buckets": {key: request.get(key) for key in ("calculation_type", "group_column", "left", "right")},
        "rows_analyzed": counts if counts is not None else "Not recorded in upstream output",
        "aggregation_or_function": request.get("aggregation") or original.get("aggregation") or raw.get("algorithm") or name,
        "computed_values": result.get("computed_values") or result.get("key_evidence") or {
            "original": original, "stressed": stressed,
            "aggregate": result.get("overall_change"), "segments": result.get("segment_results"),
            "weights": result.get("segment_weights"), "mix_shift": result.get("mix_shift_evidence"),
        },
        "formula_or_rule": rule,
        "result": result.get("final_status") or result.get("status") or result.get("finding"),
        "comparison": result.get("comparison"),
        "difference": result.get("difference"),
        "limitations": result.get("limitations") or context.get("limitations") or ["No additional limitations recorded upstream."],
        "dataset_fingerprint": upstream_fingerprint or dataset_fingerprint or "Not recorded in upstream output",
        "fingerprint_basis": "Upstream pandas-row SHA-256" if upstream_fingerprint else (
            "Caller-supplied fingerprint; Streamlit uses SHA-256 of uploaded CSV bytes" if dataset_fingerprint else "Not recorded"),
        "upstream_receipt": raw,
        "stress_rows_analyzed": stressed.get("row_counts") if isinstance(stressed, dict) else None,
    })
