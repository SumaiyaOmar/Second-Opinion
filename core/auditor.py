"""Translate a claim and a user-confirmed interpretation into a calculation request."""

from dataclasses import dataclass

import pandas as pd

from tools.analytics import audit_dataset, inconclusive_result


@dataclass(frozen=True)
class AuditRequest:
    calculation_type: str
    metric: str
    aggregation: str
    operator: str
    group_column: str | None = None
    left: str | None = None
    right: str | None = None
    target: float | None = None
    target_kind: str = "absolute"


def suggest_mapping(claim: dict, data: pd.DataFrame) -> dict:
    """Suggest exact column-name matches only; never guess synonyms or periods."""
    metric = (claim.get("metric") or "").strip().casefold()
    matches = [column for column in data.columns if str(column).strip().casefold() == metric]
    return {
        "metric": matches[0] if len(matches) == 1 else None,
        "requires_confirmation": True,
        "reason": (
            "Confirm the aggregation, scope, and assertion before calculating."
            if len(matches) == 1 else
            "Metric column is missing or ambiguous. Confirm the column mapping and assertion."
        ),
    }


def build_audit_request(claim: dict, data: pd.DataFrame, confirmed: dict | None = None) -> AuditRequest:
    """Require explicit interpretation because the extraction omits aggregation/targets."""
    if claim.get("claim_type") not in {"number", "comparison"}:
        raise ValueError("Only simple numeric and comparison claims are supported.")
    if not confirmed or confirmed.get("confirmed") is not True:
        raise ValueError(suggest_mapping(claim, data)["reason"])
    request = AuditRequest(**{key: value for key, value in confirmed.items() if key != "confirmed"})
    return request


def audit_claim(data: pd.DataFrame, claim: dict, confirmed: dict | None = None) -> dict:
    """Return a safe inconclusive result until the calculation is fully specified."""
    try:
        request = build_audit_request(claim, data, confirmed)
    except (TypeError, ValueError) as exc:
        return inconclusive_result(claim.get("metric"), str(exc))
    return audit_dataset(data, request)
