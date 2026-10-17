"""Presentation of existing structured results; no analysis or model calls."""

from copy import deepcopy

import streamlit as st

from tools.receipts import computational_receipt
from tools.visuals import evidence_charts
from ui.evidence import show_chart, show_proof
from ui.reveals import result_reveals, evidence_cards, text
from ui.audit_summary import audit_summary


LABELS = {
    "metric_column": "Metric", "time_column": "Comparison field",
    "baseline_bucket": "Baseline", "comparison_bucket": "Compare",
    "segment_column": "Segment", "aggregation": "Aggregation",
    "alternative_window": "Alternative-window check",
    "leave_one_segment_out": "Leave-one-segment-out test",
    "outlier_removal": "Outlier-removal check", "mean_vs_median": "Mean vs median",
    "bootstrap": "Bootstrap resampling check",
    "direction_reversal": "Aggregate and segment trends disagree",
    "mix_shift": "Change in segment composition",
    "no_material_mix_effect": "No material change from segment composition",
    "inconclusive": "Insufficient evidence for a segment conclusion",
}


def label(name):
    return LABELS.get(name, name.replace("_", " ").capitalize())


def mapping_summary(mapping, confirmed_mapping=None, audit=None):
    mapping = deepcopy(mapping)
    used = (confirmed_mapping or {}).get("confirmed") is True and (audit or {}).get("status") in {
        "Supported", "Partially supported", "Unsupported"}
    if used:
        # Display the user's submitted values, without changing mapper output.
        resolved = set()
        for field, request_field in (("metric_column", "metric"), ("time_column", "group_column"),
                                     ("comparison_bucket", "left"), ("baseline_bucket", "right"),
                                     ("aggregation", "aggregation")):
            value = confirmed_mapping.get(request_field)
            if value is not None:
                mapping[field] = value
                mapping.setdefault("field_validity", {})[field] = {"status": "valid"}
                resolved.add(field)
        mapping["confirmation_fields"] = [f for f in mapping.get("confirmation_fields", []) if f not in resolved]
        mapping["needs_confirmation"] = bool(mapping["confirmation_fields"])
    st.write("**Confirmed mapping**" if used else "**Proposed mapping**")
    pending = mapping.get("confirmation_fields", [])
    fields = ("metric_column", "comparison_bucket", "baseline_bucket", "segment_column", "aggregation")
    columns = st.columns(len(fields))
    for column, field in zip(columns, fields):
        value = mapping.get(field)
        validity = mapping.get("field_validity", {}).get(field, {}).get("status")
        optional_segment = (field == "segment_column" and field not in pending and value is None
                            and validity in {None, "not_required"})
        column.caption(label(field))
        column.write(str(value) if value is not None else "Not required / not selected" if optional_segment else "Not selected")
        if field in pending or validity in {"invalid", "ambiguous", "unresolved"} or (value is None and not optional_segment):
            column.markdown('<span class="so-mapping-status pending">Needs confirmation</span>', unsafe_allow_html=True)
        elif optional_segment or validity == "not_required":
            column.caption("Optional — no action needed")
        else:
            column.markdown('<span class="so-mapping-status mapped">✓ mapped</span>', unsafe_allow_html=True)
    if mapping.get("needs_confirmation"):
        st.warning("Please confirm: " + ", ".join(label(f) for f in pending) if pending
                   else "Please review the proposed mapping before continuing.")
    elif used:
        st.caption("Confirmed mapping used by the number check.")
    else:
        st.caption("Review the proposed calculation and confirm that it represents your full claim.")


def stress_details(critic, audit, investigation, mapping):
    with st.expander("View stress-test details", expanded=False):
        charts = evidence_charts(audit, investigation, critic)
        for check in critic["checks_run"]:
            st.write(f"**{label(check['name'])} · {label(check['status'])}**")
            st.write(check["interpretation"])
            if check["name"] in {"mean_vs_median", "outlier_removal"}:
                if charts[check["name"]] is not None:
                    show_chart(charts[check["name"]])
            show_proof(computational_receipt(check["name"], check, mapping=mapping, context=critic),
                       f"Show proof: {label(check['name'])}")
        with st.expander("Technical details: stress tests", expanded=False):
            st.json(critic)


def stability(critic):
    st.subheader("Stability")
    st.caption("What would make this conclusion wrong?")
    if not critic:
        st.info("Stress tests have not been run.")
        return
    st.write(critic["stability_summary"])
    for check in critic["checks_run"]:
        if check["status"] == "failed":
            st.warning(f"Failed: {label(check['name'])}. {check['interpretation']}")
        elif check["status"] == "inconclusive":
            st.caption(f"Inconclusive: {label(check['name'])}")


def verdict_panel(result, audit, investigation, critic, mapping, fingerprint):
    result_reveals(audit, investigation)
    with st.container(border=True, key="verdict_card"):
        status_class = {"Supported": "supported", "Partially supported": "partial",
                        "Unsupported": "unsupported", "Inconclusive": "inconclusive"}.get(result["final_status"], "inconclusive")
        st.markdown(f'<span class="so-verdict-badge {status_class}">{text(result["final_status"].upper())}</span>',
                    unsafe_allow_html=True)
        st.subheader(f"Final verdict: {result['final_status']}")
        st.write("**Original claim**")
        st.write(result["original_claim"])
        st.write("**Verified version**")
        st.write(result["corrected_conclusion"])

    evidence_cards(result, audit, investigation, critic, mapping)
    st.subheader("Key evidence")
    charts = evidence_charts(audit, investigation, critic)
    aggregate_panel, segment_panel = st.columns(2, gap="large")
    if charts["aggregate"] is not None:
        with aggregate_panel, st.container(border=True, key="chart_aggregate"):
            st.write("**Aggregate comparison**")
            show_chart(charts["aggregate"], kind="aggregate")
    if investigation:
        st.write(f"**{label(investigation['finding'])}**")
        if charts["segments"] is not None:
            with segment_panel, st.container(border=True, key="chart_segments"):
                st.write("**Within each segment**")
                show_chart(charts["segments"], kind="segments")
            with st.container(border=True, key="chart_composition"):
                st.write("**Change in segment composition**")
                show_chart(charts["composition"], kind="composition")
        if investigation.get("mix_shift_evidence"):
            st.write(investigation["mix_shift_evidence"]["explanation"])
    st.write(audit_summary(audit, mapping))
    stability(critic)
    supported, unsupported = st.columns(2)
    for column, title, key in ((supported, "What is supported", "what_is_supported"),
                               (unsupported, "What is not supported", "what_is_not_supported")):
        with column:
            st.write(f"**{title}**")
            for item in dict.fromkeys(result[key]):
                st.write(item)
    if result["limitations"]:
        st.info("Important limitation: " + result["limitations"][0])
    show_proof(computational_receipt("verdict", result, mapping=mapping,
               dataset_fingerprint=fingerprint), "Show proof: final verdict")
    if critic:
        stress_details(critic, audit, investigation, mapping)
    with st.expander("Technical details: final verdict", expanded=False):
        st.json(result)
