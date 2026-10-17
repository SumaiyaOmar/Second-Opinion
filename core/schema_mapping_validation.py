"""Independent field validation/recovery; structured state owns the explanation."""

import re


FIELD_NAMES = ("metric_column", "time_column", "baseline_bucket", "comparison_bucket", "segment_column", "aggregation")


def segmentation_requested(claim, extracted, upstream=False, user_confirmed=False):
    if upstream or user_confirmed:
        return True
    text = claim.casefold()
    if re.search(r"\b(no|without|do not)\s+(any\s+)?(segment\w*|group\w*|breakdown|stratif\w*)", text):
        return False
    return bool(re.search(r"\b(groups?|segments?|categor(?:y|ies)|cohorts?|subpopulations?|strata|stratum|stratified|mix|breakdown)\b|\b(within|for) each\b|\bby (region|channel|tier|department|branch|size|treatment)\b", text))


def recover_fields(proposal, data, claim, extracted, profile, bucket_resolver,
                   failure_reason=None, upstream=False, user_confirmed=False):
    """Retain valid siblings. Recover only unique literal/schema facts, not guesses."""
    known = {c["name"]: c for c in profile["columns"]}
    proposed = proposal if isinstance(proposal, dict) else {}
    result = {field: None for field in FIELD_NAMES}
    result.update(candidate_alternatives=[], needs_confirmation=False, ambiguities=[], reasoning_summary="")
    validity = {}
    diagnostics = []
    if failure_reason:
        diagnostics.append({"reason": failure_reason, "field": None})

    def state(field, status, reason):
        validity[field] = {"status": status, "reason": reason}

    def invalidate(field, reason):
        result[field] = None
        state(field, "invalid", reason)
        diagnostics.append({"reason": "candidate_validation_failure", "field": field})

    # Alternatives are role-specific and never allowed to invalidate unrelated roles.
    raw_alternatives = proposed.get("candidate_alternatives", [])
    if not isinstance(raw_alternatives, list):
        diagnostics.append({"reason": "schema_validation_failure", "field": "candidate_alternatives"})
        raw_alternatives = []
    for alternative in raw_alternatives[:20]:
        if not isinstance(alternative, dict):
            continue
        role, column = alternative.get("role"), alternative.get("column")
        if role not in {"metric", "time", "segment"} or not isinstance(column, str) or column not in known:
            diagnostics.append({"reason": "candidate_validation_failure", "field": "candidate_alternatives"})
            continue
        if role == "metric" and not known[column]["numeric"]:
            continue
        if role == "segment" and known[column]["numeric"]:
            continue
        if {"role": role, "column": column} not in result["candidate_alternatives"]:
            result["candidate_alternatives"].append({"role": role, "column": column})

    for field in ("metric_column", "time_column", "segment_column"):
        value = proposed.get(field)
        if value is None:
            state(field, "unresolved", "No validated selection.")
        elif not isinstance(value, str) or value not in known or list(data.columns).count(value) != 1:
            invalidate(field, "Selection is not an unambiguous available column.")
        elif field == "metric_column" and not known[value]["numeric"]:
            invalidate(field, "Numerical audit requires a numeric non-boolean metric.")
        elif field == "time_column" and known[value]["numeric"]:
            invalidate(field, "Numeric measures are not inferred to be time/bucket columns.")
        elif field == "segment_column" and (known[value]["numeric"] or known[value]["unique_count"] < 2):
            invalidate(field, "Segment needs at least two categorical values.")
        else:
            result[field] = value
            state(field, "valid", "Available role-compatible column.")

    # Independent time recovery: one ISO time field with a unique literal pair.
    if result["time_column"] is None and validity["time_column"]["status"] != "invalid":
        candidates = [c for c in profile["columns"] if c["is_iso_time"] and bucket_resolver(claim, c["values"])]
        if len(candidates) == 1:
            result["time_column"] = candidates[0]["name"]
            state("time_column", "valid", "Recovered unique ISO time field with claim-matched buckets.")

    # Recover metric only from a unique exact extracted/name/description match.
    if result["metric_column"] is None and validity["metric_column"]["status"] != "invalid":
        metric = (extracted.get("metric") or "").strip().casefold()
        exact = [c["name"] for c in profile["columns"] if c["numeric"] and (
            c["name"].casefold() == metric or re.search(r"(?<!\w)" + re.escape(c["name"].casefold()) + r"(?!\w)", claim.casefold()))]
        if len(exact) == 1:
            result["metric_column"] = exact[0]
            state("metric_column", "valid", "Recovered unique literal metric column.")

    time = result["time_column"]
    if time and result["metric_column"] == time:
        invalidate("time_column", "Time and metric roles must be distinct.")
        time = None
    observed = set(data[time].dropna().astype(str)) if time else set()
    justified = bucket_resolver(claim, known[time]["values"]) if time else None
    for field, index in (("baseline_bucket", 0), ("comparison_bucket", 1)):
        value = proposed.get(field)
        if value is not None:
            if not isinstance(value, str) or value not in observed:
                invalidate(field, "Bucket does not occur in the validated time/bucket column.")
            else:
                result[field] = value
                state(field, "valid" if justified and justified[index] == value else "ambiguous",
                      "Claim ordering matches observed label." if justified and justified[index] == value else "Confirm bucket ordering against the claim.")
        elif justified:
            result[field] = justified[index]
            state(field, "valid", "Recovered uniquely claim-matched observed bucket.")
        else:
            state(field, "unresolved", "Bucket requires confirmation.")
    if result["baseline_bucket"] is not None and result["baseline_bucket"] == result["comparison_bucket"]:
        invalidate("comparison_bucket", "Comparison must use two distinct buckets.")

    aggregation = proposed.get("aggregation")
    if aggregation in ("mean", "sum"):
        result["aggregation"] = aggregation
        state("aggregation", "valid", "Supported aggregation.")
    elif aggregation is not None:
        invalidate("aggregation", "Unsupported aggregation.")
    elif re.search(r"\b(average|mean)\b", claim, re.I):
        result["aggregation"] = "mean"
        state("aggregation", "valid", "Recovered explicit average/mean wording.")
    elif re.search(r"\b(total|sum)\b", claim, re.I):
        result["aggregation"] = "sum"
        state("aggregation", "valid", "Recovered explicit total/sum wording.")
    else:
        state("aggregation", "unresolved", "Confirm aggregation; numeric dtype does not determine it.")

    segment_needed = segmentation_requested(claim, extracted, upstream, user_confirmed)
    segment = result["segment_column"]
    # Extracted entity names can imply subpopulation comparison only if they
    # match actual categorical values outside the time field.
    entities = extracted.get("entities_or_segments") or []
    if not segment_needed and segment and isinstance(entities, list):
        values = set(data[segment].dropna().astype(str))
        segment_needed = bool(entities and all(isinstance(e, str) and e in values for e in entities))
    if not segment_needed:
        result["segment_column"] = None
        state("segment_column", "not_required", "Claim does not request segmentation; proposed segment removed.")
        result["candidate_alternatives"] = [a for a in result["candidate_alternatives"] if a["role"] != "segment"]
    elif segment:
        if segment in {result["metric_column"], time}:
            invalidate("segment_column", "Segment must be distinct from time and metric.")
        elif not time or any(validity[f]["status"] != "valid" for f in ("baseline_bucket", "comparison_bucket")):
            state("segment_column", "unresolved", "Segment usability depends on confirmed buckets.")
        else:
            metric = result["metric_column"]
            selected = data.loc[data[time].astype(str).isin([result["baseline_bucket"], result["comparison_bucket"]])].copy()
            selected[time] = selected[time].astype(str)
            counts = selected.groupby([time, segment], dropna=False).size().unstack(time, fill_value=0)
            enough = counts.reindex(columns=[result["baseline_bucket"], result["comparison_bucket"]], fill_value=0).ge(2).all(axis=1)
            if metric and selected[metric].isna().any() or selected[segment].isna().any() or len(enough) < 2 or not enough.all():
                state("segment_column", "ambiguous", "Need two usable groups with two observations per bucket.")
    else:
        state("segment_column", "unresolved", "Confirm the requested grouping.")

    numeric = [c["name"] for c in profile["columns"] if c["numeric"]]
    categorical = [c["name"] for c in profile["columns"] if not c["numeric"] and c["name"] != time and c["unique_count"] >= 2]
    if re.search(r"\bperformance\b", claim, re.I) and len(numeric) > 1:
        for column in numeric:
            if {"role": "metric", "column": column} not in result["candidate_alternatives"]:
                result["candidate_alternatives"].append({"role": "metric", "column": column})
    if segment_needed and re.search(r"\b(groups?|segments?|categor(?:y|ies))\b", claim, re.I) and len(categorical) > 1 and not user_confirmed:
        for column in categorical:
            if {"role": "segment", "column": column} not in result["candidate_alternatives"]:
                result["candidate_alternatives"].append({"role": "segment", "column": column})
    for role, field in (("metric", "metric_column"), ("time", "time_column"), ("segment", "segment_column")):
        if role == "segment" and user_confirmed and validity[field]["status"] == "valid":
            continue
        if len({a["column"] for a in result["candidate_alternatives"] if a["role"] == role}) > 1:
            result[field] = None
            state(field, "ambiguous", f"Multiple plausible {role} columns require confirmation.")
    uncertain = proposed.get("uncertain_fields", [])
    if isinstance(uncertain, list):
        for field in uncertain:
            if isinstance(field, str) and field in FIELD_NAMES:
                if field == "segment_column" and not segment_needed:
                    continue
                if field == "segment_column" and user_confirmed and validity[field]["status"] == "valid":
                    continue
                if validity[field]["status"] == "valid":
                    state(field, "ambiguous", "Model identified uncertainty in this field; confirm its interpretation.")
            else:
                diagnostics.append({"reason": "schema_validation_failure", "field": "uncertain_fields"})
    else:
        diagnostics.append({"reason": "schema_validation_failure", "field": "uncertain_fields"})
    if validity["time_column"]["status"] != "valid":
        for field in ("baseline_bucket", "comparison_bucket"):
            if validity[field]["status"] == "valid":
                result[field] = None
                state(field, "unresolved", "Bucket depends on the unresolved time/bucket column.")

    required = {"metric_column", "aggregation"}
    if extracted.get("claim_type") in {"comparison", "causal"}:
        required.update(("time_column", "baseline_bucket", "comparison_bucket"))
    if segment_needed:
        required.add("segment_column")
    confirmations = [f for f in FIELD_NAMES if f in required and validity[f]["status"] not in {"valid", "not_required"}]
    result.update(field_validity=validity, confirmation_fields=confirmations,
                  needs_confirmation=bool(confirmations),
                  ambiguities=[f"{field}: {validity[field]['reason']}" for field in confirmations],
                  internal_diagnostics=diagnostics)
    # Free-form model prose is deliberately ignored.
    parts = []
    for field in FIELD_NAMES:
        value = result[field]
        status = validity[field]["status"]
        if field == "segment_column" and status == "not_required":
            parts.append("No segment selected; segmentation was not requested.")
        elif value is not None:
            parts.append(f"{field} = {value!r} ({status}).")
        else:
            parts.append(f"{field} requires confirmation." if field in confirmations else f"{field} is not selected.")
    result["reasoning_summary"] = " ".join(parts)
    return result
