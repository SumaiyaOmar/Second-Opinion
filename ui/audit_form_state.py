"""Widget ownership and immutable audit submission snapshots (UI only)."""

from copy import deepcopy


FIELDS = ("metric", "calculation_type", "aggregation", "operator", "group_column", "left", "right",
          "has_target", "target", "target_kind", "confirmed")


def widget_keys(revision):
    return {field: f"audit_input_{revision}_{field}" for field in FIELDS}


def initialize_widgets(state, keys, proposal, metric_suggestion):
    accepted = state.get("audit_mapping") or {}
    defaults = dict(metric=proposal.get("metric_column") or metric_suggestion,
                    calculation_type="two_periods" if proposal.get("time_column") else None,
                    aggregation=proposal.get("aggregation"), operator=None,
                    group_column=proposal.get("time_column"), left=proposal.get("comparison_bucket") or "",
                    right=proposal.get("baseline_bucket") or "", has_target=False, target=0.0,
                    target_kind="absolute", confirmed=False)
    defaults.update(accepted)
    defaults["has_target"] = accepted.get("target") is not None
    defaults["target"] = float(accepted["target"]) if accepted.get("target") is not None else 0.0
    previous_defaults = state.setdefault("_audit_widget_defaults", {})
    edited = state.get("_audit_edited_fields", [])
    for field, key in keys.items():
        untouched = key not in edited and state.get(key) == previous_defaults.get(key)
        if key not in state or (untouched and defaults[field] != previous_defaults.get(key)):
            state[key] = defaults[field]
        previous_defaults[key] = defaults[field]


def mark_edited(state, key):
    fields = list(state.get("_audit_edited_fields", []))
    if key not in fields:
        fields.append(key)
    state["_audit_edited_fields"] = fields


def capture_submission(state, keys):
    """Runs as the submit callback, before any rerender can change defaults."""
    values = {field: deepcopy(state.get(key)) for field, key in keys.items()}
    overall = values["calculation_type"] == "overall"
    request = {field: values[field] for field in ("confirmed", "calculation_type", "metric", "aggregation", "operator", "target_kind")}
    request.update(group_column=None if overall else values["group_column"],
                   left=None if overall else values["left"], right=None if overall else values["right"],
                   target=values["target"] if values["has_target"] else None)
    # Presence/type checks only; analytical validation remains in the Auditor.
    missing = [field for field in ("metric", "calculation_type", "aggregation", "operator") if request[field] is None]
    state["audit_submission"] = {"request": request, "missing_fields": missing,
                                 "widget_values": values}


def submitted_request(state):
    return deepcopy(state["audit_submission"]["request"])
