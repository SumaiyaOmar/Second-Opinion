"""UI dependency invalidation. No analytical rules or calculations."""

import hashlib


AFTER_AUDIT = ("investigation_result", "investigation_request", "investigation_skipped", "stress_not_applicable",
               "critic_result", "verdict_result", "investigation_segment", "investigation_confirmed",
               "critic_segment", "critic_confirmed")
AFTER_AUDIT += ("_investigation_segment_widget", "_investigation_confirmed_widget", "investigation_input_error",
                "_pending_scroll_target")
AFTER_CLAIM = ("extracted_claim", "schema_mapping_result", "schema_mapping_signature",
               "audit_mapping", "audit_submission", "audit_result", "_audit_widget_defaults", "_audit_edited_fields", *AFTER_AUDIT)


def clear_keys(state, keys):
    for key in keys:
        state.pop(key, None)


def set_dataset(state, payload, preserve_claim=False):
    """Own immutable CSV bytes; a widget's cursor is never the dataset state."""
    dataset_id = hashlib.sha256(payload).hexdigest()
    if state.get("dataset_id") != dataset_id:
        clear_keys(state, AFTER_CLAIM)
        state["mapping_form_revision"] = state.get("mapping_form_revision", 0) + 1
        state.pop("_claim_snapshot", None)
        if not preserve_claim:
            state.pop("claim_input", None)
    state["dataset_id"] = dataset_id
    state["dataset_bytes"] = payload


def clear_dataset(state):
    clear_keys(state, (*AFTER_CLAIM, "dataset_id", "dataset_bytes", "claim_input", "_claim_snapshot"))
    state["mapping_form_revision"] = state.get("mapping_form_revision", 0) + 1


def sync_claim(state, claim):
    previous = state.get("_claim_snapshot", (state.get("extracted_claim") or {}).get("original_claim", claim))
    if previous != claim:
        clear_keys(state, AFTER_CLAIM)
        state["mapping_form_revision"] = state.get("mapping_form_revision", 0) + 1
    state["_claim_snapshot"] = claim


def store_audit(state, mapping, result):
    if state.get("audit_mapping") != mapping or state.get("audit_result") != result:
        clear_keys(state, AFTER_AUDIT)
    state["audit_mapping"] = mapping
    state["audit_result"] = result
