"""Persist investigation inputs before any analytical call (UI only)."""

from copy import deepcopy


SEGMENT_WIDGET = "_investigation_segment_widget"
CONFIRMED_WIDGET = "_investigation_confirmed_widget"


def initialize_investigation(state, suggested=None):
    # Durable values must never be registered directly as Streamlit widgets:
    # Streamlit deletes widget-owned keys when a conditional stage is hidden.
    if "investigation_segment" not in state:
        state["investigation_segment"] = suggested
    else:
        # Detach legacy sessions where this durable name was a widget key.
        state["investigation_segment"] = state["investigation_segment"]
    if "investigation_confirmed" not in state:
        state["investigation_confirmed"] = False
    else:
        state["investigation_confirmed"] = state["investigation_confirmed"]
    if SEGMENT_WIDGET not in state:
        state[SEGMENT_WIDGET] = state["investigation_segment"]
    if CONFIRMED_WIDGET not in state:
        state[CONFIRMED_WIDGET] = state["investigation_confirmed"]


def persist_investigation_inputs(state):
    if SEGMENT_WIDGET in state:
        state["investigation_segment"] = state[SEGMENT_WIDGET]
    if CONFIRMED_WIDGET in state:
        state["investigation_confirmed"] = state[CONFIRMED_WIDGET]


def capture_investigation(state):
    persist_investigation_inputs(state)
    state["investigation_request"] = deepcopy({
        "segment_column": state.get("investigation_segment"),
        "segment_confirmed": state.get("investigation_confirmed", False),
        "audit_mapping": state.get("audit_mapping"), "audit_result": state.get("audit_result"),
        "claim": state.get("extracted_claim"), "dataset_id": state.get("dataset_id"),
    })


def successful_investigation(result):
    return bool(result and (result.get("computational_receipt") or {}).get("executed") is True
                and result.get("finding") in {"direction_reversal", "mix_shift", "no_material_mix_effect"})
