"""Streamlit presentation for the Second Opinion analysis pipeline."""

import pandas as pd
import streamlit as st
import hashlib
import io
from copy import deepcopy
from pathlib import Path

from core.claims import ClaimExtractionError, extract_claim
from core.auditor import audit_claim, suggest_mapping
from core.investigator import investigate_segments
from core.critic import run_critic
from core.verdict import generate_verdict
from core.schema_mapper import map_schema
from tools.analytics import profile_dataset
from tools.receipts import computational_receipt
from ui.evidence import show_proof
from ui.results import mapping_summary, verdict_panel, stability, stress_details, label
from ui.style import apply_theme
from ui.reveals import progress
from ui.story import hero_visual
from ui.site import navigation, workflow, information_sections
from ui.interactions import scroll_to_inputs, scroll_to_section
from ui.audit_summary import audit_summary
from ui.session import set_dataset, clear_dataset, sync_claim, store_audit
from ui.audit_form_state import widget_keys, initialize_widgets, capture_submission, submitted_request, mark_edited
from ui.investigation_form_state import (capture_investigation, initialize_investigation,
    persist_investigation_inputs, successful_investigation, SEGMENT_WIDGET, CONFIRMED_WIDGET)


def show_schema_mapping(data, extracted):
    st.subheader("Confirm the comparison")
    if "suggest_schema_mapping" not in st.session_state:
        st.session_state["suggest_schema_mapping"] = True
    request_mapping = st.toggle("Suggest mappings using non-sensitive schema labels",
                                key="suggest_schema_mapping",
                                help="Enable only if low-cardinality categorical labels are safe to share with Nebius. Identifier-like columns are withheld.")
    signature = (st.session_state.get("dataset_id"), extracted["original_claim"])
    if request_mapping and st.session_state.get("schema_mapping_signature") != signature:
        with st.spinner("Mapping schema…"):
            result = map_schema(extracted["original_claim"], extracted, data, safe_columns=list(data.columns))
        st.session_state["schema_mapping_result"] = result
        st.session_state["schema_mapping_signature"] = signature
    result = st.session_state.get("schema_mapping_result")
    return result



def investigation_eligible(extracted, audit):
    return (extracted["claim_type"] == "comparison" and audit["status"] != "Inconclusive"
            and audit["calculation_type"] in {"two_periods", "two_groups"})


def demo_segment(data):
    if (st.session_state.get("demo_mode") and "segment" in data.columns
            and st.session_state.get("dataset_id") == hashlib.sha256(
                (Path(__file__).resolve().parent / "data/synthetic_simpson.csv").read_bytes()).hexdigest()):
        return "segment"
    return None


def show_verdict(extracted, audit, result_area=None):
    if (extracted["claim_type"] in {"number", "comparison"}
            and not st.session_state.get("critic_result") and not st.session_state.get("stress_not_applicable")):
        return
    verdict_area = result_area if result_area is not None else st.container()
    existing = st.session_state.get("verdict_result")
    if not existing:
        st.subheader("Final Verdict")
    if st.button("Generate final verdict", type="secondary" if existing else "primary", disabled=bool(existing)):
        # Commit the deterministic result before any optional provider work.
        # Snapshot durable upstream evidence, rather than widget return values.
        inputs = deepcopy((st.session_state.get("extracted_claim", extracted),
                           st.session_state.get("audit_result", audit),
                           st.session_state.get("investigation_result"),
                           st.session_state.get("critic_result")))
        st.session_state["verdict_result"] = generate_verdict(*inputs, use_model=False)
        with st.spinner("Preparing verified conclusion..."):
            try:
                st.session_state["verdict_result"] = generate_verdict(*inputs)
            except Exception:
                # Keep the already committed verdict; never display exception text.
                st.session_state["verdict_result"]["computational_receipts"]["explanation_source"] = "deterministic_fallback"
        st.session_state["_pending_scroll_target"] = "final-verdict-result-section"
        st.session_state.pop("_demo_scroll_pending", None)
        st.rerun()
    result = st.session_state.get("verdict_result")
    if result:
        with verdict_area:
            st.markdown('<div id="final-verdict-result-section" class="so-section-anchor"></div>', unsafe_allow_html=True)
            st.subheader("Final Verdict")
            if result.get("computational_receipts", {}).get("explanation_source") == "deterministic_fallback":
                st.info("Model wording was unavailable. The deterministic verdict and verified conclusion are shown below.")
            verdict_panel(result, audit, st.session_state.get("investigation_result"),
                          st.session_state.get("critic_result"), st.session_state.get("audit_mapping"),
                          st.session_state.get("dataset_id"))



def show_critic(data, extracted, audit):
    if not st.session_state.get("audit_result") or audit["status"] == "Inconclusive":
        return
    if (investigation_eligible(extracted, audit) and not st.session_state.get("investigation_result")
            and not st.session_state.get("investigation_skipped")):
        return
    st.markdown('<div id="stress-test-section" class="so-section-anchor"></div>', unsafe_allow_html=True)
    st.subheader("Self-Doubt / Stress Test", anchor="stress-test-heading")
    st.write("What would make this conclusion wrong?")
    investigation = st.session_state.get("investigation_result")
    receipt = (investigation or {}).get("computational_receipt", {})
    with st.form("critic_confirmation"):
        options = [None, *list(data.columns)]
        suggested = receipt.get("segment_column") or demo_segment(data)
        segment = st.selectbox("Segment column for leave-one-out (optional)", options,
                               index=options.index(suggested) if suggested in options else 0, key="critic_segment")
        confirmed = st.checkbox("I confirm the segment mapping for stress tests.", value=bool(suggested), key="critic_confirmed")
        run = st.form_submit_button("Run stress tests", type="secondary" if st.session_state.get("critic_result") else "primary")
    if run:
        st.session_state.pop("verdict_result", None)
        st.session_state["critic_result"] = run_critic(
            data, extracted, audit, st.session_state.get("audit_mapping"), segment, confirmed,
            investigation_result=investigation if receipt.get("executed") else None,
        )
    result = st.session_state.get("critic_result")
    if result and not st.session_state.get("verdict_result"):
        stability(result)
        stress_details(result, audit, investigation, st.session_state.get("audit_mapping"))



def show_investigation(data, extracted, audit):
    if not st.session_state.get("audit_result") or not investigation_eligible(extracted, audit):
        return
    st.subheader("Investigation", anchor="live-investigation-section")
    st.write("Original claim:", extracted["original_claim"])
    st.write("Audit verdict:", audit["status"])
    initialize_investigation(st.session_state, demo_segment(data))
    with st.container(key="investigation_confirmation"):
        st.selectbox("Segment column for breakdown", list(data.columns), index=None, key=SEGMENT_WIDGET,
                     on_change=persist_investigation_inputs, args=(st.session_state,))
        st.caption("Each row must be one equally weighted observation. At least two segments need two complete observations in each bucket. Pre-aggregated rates are not supported.")
        st.checkbox("I confirm this segment column and observation granularity.", key=CONFIRMED_WIDGET,
                    on_change=persist_investigation_inputs, args=(st.session_state,))
        run = st.button("Investigate hidden pattern", key="run_investigation", type="primary",
                        on_click=capture_investigation, args=(st.session_state,))
    if run:
        st.session_state.pop("_pending_scroll_target", None)
        st.session_state.pop("_demo_scroll_pending", None)
        st.session_state.pop("investigation_skipped", None)
        st.session_state.pop("critic_result", None)
        st.session_state.pop("verdict_result", None)
        request = st.session_state["investigation_request"]
        if request["segment_column"] not in data.columns or request["segment_confirmed"] is not True:
            st.session_state.pop("investigation_result", None)
            st.session_state["investigation_input_error"] = "Select and confirm the segment column before investigation."
        else:
            st.session_state.pop("investigation_input_error", None)
            st.session_state["investigation_result"] = investigate_segments(
                data, request["claim"], request["audit_result"], request["audit_mapping"],
                segment_column=request["segment_column"], segment_confirmed=request["segment_confirmed"],
            )
            if successful_investigation(st.session_state["investigation_result"]):
                st.session_state["_pending_scroll_target"] = "stress-test-section"
            # Render the stored result on a fresh pass before dispatching scroll.
            st.rerun()
    if st.session_state.get("investigation_input_error"):
        st.warning(st.session_state["investigation_input_error"])
    result = st.session_state.get("investigation_result")
    if st.button("Skip investigation", type="secondary"):
        st.session_state["investigation_skipped"] = True
        st.session_state.pop("investigation_result", None)
        st.session_state.pop("critic_result", None)
        st.session_state.pop("verdict_result", None)
        result = None
    if st.session_state.get("investigation_skipped"):
        st.info("Investigation was explicitly skipped. Segment patterns have not been assessed.")
    if result:
        st.write(label(result["finding"]))
        if result.get("mix_shift_evidence"):
            st.write(result["mix_shift_evidence"]["explanation"])
        with st.expander("Technical details: investigation", expanded=False):
            st.json(result)
            show_proof(computational_receipt("segment_investigation", result,
                       mapping=st.session_state.get("audit_mapping")), "View computational receipt")



def show_audit(data, extracted):
    result_area = st.container()
    initial = audit_claim(data, extracted)
    if extracted["claim_type"] not in {"number", "comparison"}:
        show_verdict(extracted, initial)
        with st.expander("Technical details: audit", expanded=False):
            st.json(extracted)
            if st.session_state.get("schema_mapping_result"):
                st.json(st.session_state["schema_mapping_result"])
            st.json(initial)
        return
    mapping = suggest_mapping(extracted, data)
    proposal = st.session_state.get("schema_mapping_result") or {}
    metric_suggestion = proposal.get("metric_column") or mapping["metric"]
    st.caption("Review the mapping to verify the claim.")
    needs_review = not st.session_state.get("audit_result") and (proposal.get("needs_confirmation") or not proposal)
    if needs_review:
        st.info("Review or change mapping — confirm the highlighted fields to verify the numbers.")
    keys = widget_keys(st.session_state.get("mapping_form_revision", 0))
    initialize_widgets(st.session_state, keys, proposal, metric_suggestion)
    with st.expander("Review or change mapping", expanded=bool(needs_review)):
        st.caption("Confirm that this calculation fully represents your claim, including scope, units, aggregation, and any stated amount. Overall uses every uploaded row; periods/groups use exact column values.")
        with st.container(key=f"audit_confirmation_{st.session_state.get('mapping_form_revision', 0)}"):
            st.selectbox("Metric", list(data.columns), index=None, key=keys["metric"], on_change=mark_edited, args=(st.session_state, keys["metric"]))
            st.selectbox("Calculation type", ["overall", "two_periods", "two_groups"], index=None, key=keys["calculation_type"], on_change=mark_edited, args=(st.session_state, keys["calculation_type"]),
                                format_func=lambda value: {"overall": "Overall metric", "two_periods": "Two periods", "two_groups": "Two groups"}[value])
            st.selectbox("Aggregation", ["sum", "mean"], index=None, key=keys["aggregation"], on_change=mark_edited, args=(st.session_state, keys["aggregation"]))
            st.selectbox("Claimed relationship: comparison vs baseline (or overall vs target)", ["greater", "less", "equal"], index=None, key=keys["operator"], on_change=mark_edited, args=(st.session_state, keys["operator"]))
            # Free-text exact values allow all inputs to remain in one confirmation form.
            group_options = [None, *list(data.columns)]
            st.selectbox("Comparison field", group_options, index=None, key=keys["group_column"], on_change=mark_edited, args=(st.session_state, keys["group_column"]))
            st.caption("Compare is the subject/current period; Baseline is the reference. Enter values exactly as shown in the CSV preview.")
            st.text_input("Compare", value=None, key=keys["left"], on_change=mark_edited, args=(st.session_state, keys["left"]))
            st.text_input("Baseline", value=None, key=keys["right"], on_change=mark_edited, args=(st.session_state, keys["right"]))
            st.checkbox("Claim includes a numeric value or exact change (required for overall)", key=keys["has_target"], on_change=mark_edited, args=(st.session_state, keys["has_target"]))
            st.number_input("Claimed value or signed change (decreases are negative)", value=None, step=0.01, format="%.6f", key=keys["target"], on_change=mark_edited, args=(st.session_state, keys["target"]))
            st.selectbox("Comparison change units (overall always uses absolute)", ["absolute", "percent"], index=None, key=keys["target_kind"], on_change=mark_edited, args=(st.session_state, keys["target_kind"]))
            st.checkbox("I confirm these columns, buckets, and calculation represent the full claim.", key=keys["confirmed"], on_change=mark_edited, args=(st.session_state, keys["confirmed"]))
            run = st.button("Run deterministic audit", type="primary", key="run_audit",
                                        on_click=capture_submission, args=(st.session_state, keys))
    if run:
        audit_mapping = submitted_request(st.session_state)
        result = audit_claim(data, extracted, audit_mapping)
        store_audit(st.session_state, audit_mapping, result)
    result = st.session_state.get("audit_result", initial)
    if st.session_state.get("audit_result"):
        with st.expander("Analysis steps", expanded=not bool(st.session_state.get("verdict_result"))):
            st.write(f"**Number check: {result['status']}**")
            st.write(audit_summary(result, st.session_state.get("audit_mapping")))
            show_investigation(data, extracted, result)
            if not investigation_eligible(extracted, result) and result["status"] != "Inconclusive":
                st.caption("Segment investigation is not applicable to this audit. Continue to stress tests.")
            show_critic(data, extracted, result)
            if result["status"] == "Inconclusive":
                st.info("This audit is inconclusive; stress tests require a completed comparison. You can review the proof or continue to an inconclusive verdict.")
                if st.button("Continue without stress tests (not applicable)"):
                    st.session_state["stress_not_applicable"] = True
    # Keep the next action after the completed stages. Only the generated
    # conclusion belongs in the earlier result-first presentation container.
    if st.session_state.get("audit_result"):
        show_verdict(extracted, result, result_area=result_area)
    else:
        with result_area:
            st.info("Waiting for mapping confirmation. Confirm the highlighted fields to verify the numbers.")
    with st.expander("Technical details", expanded=False):
        st.write("Structured claim")
        st.json(extracted)
        if st.session_state.get("schema_mapping_result"):
            st.write("Schema mapping")
            st.json(st.session_state["schema_mapping_result"])
        st.write("Number check")
        st.json(result)
        if result.get("calculation"):
            st.code(result["calculation"], language="text")
        show_proof(computational_receipt("audit", result,
                   mapping=st.session_state.get("audit_mapping"),
                   dataset_fingerprint=st.session_state.get("dataset_id")), "Show proof: audit")



def load_demo_inputs():
    """Reset input widgets before rendering; never execute an analysis stage."""
    st.session_state["demo_mode"] = True
    st.session_state["suggest_schema_mapping"] = True
    st.session_state["claim_input"] = "The overall score increased after the change."
    st.session_state["_demo_scroll_pending"] = True
    st.session_state.pop("_pending_scroll_target", None)
    st.session_state["upload_widget_version"] = st.session_state.get("upload_widget_version", 0) + 1
    st.session_state["mapping_form_revision"] = st.session_state.get("mapping_form_revision", 0) + 1
    for key in ("schema_mapping_result", "schema_mapping_signature", "extracted_claim", "audit_result",
                "audit_mapping", "audit_submission", "investigation_result", "investigation_request", "critic_result", "verdict_result",
                "investigation_skipped", "stress_not_applicable"):
        st.session_state.pop(key, None)
    for key in ("investigation_segment", "investigation_confirmed", SEGMENT_WIDGET, CONFIRMED_WIDGET,
                "investigation_input_error"):
        st.session_state.pop(key, None)


def use_uploaded_csv():
    st.session_state["demo_mode"] = False
    st.session_state["_upload_changed"] = True


def request_input_scroll():
    st.session_state["_demo_scroll_pending"] = True
    st.session_state.pop("_pending_scroll_target", None)


def page_body():
    st.markdown('<div id="home-section" class="so-section-anchor"></div>', unsafe_allow_html=True)
    with st.container(key="hero"):
        hero_copy, hero_art = st.columns([1.05, 1], gap="large")
        with hero_copy:
            st.markdown('<div class="so-eyebrow"><span class="so-swatch"></span>AI Data Truth Engine</div>', unsafe_allow_html=True)
            st.title("Second Opinion")
            st.markdown('<p class="so-tagline">An analyst that doubts itself.</p>', unsafe_allow_html=True)
            st.write("Most AI analytics tools answer questions. Second Opinion asks whether the answer should be trusted.")
            st.caption("Upload a dataset and a business claim. Verify the numbers, uncover hidden patterns, and stress-test the conclusion.")
            upload_action, demo_action = st.columns([1, 1.6])
            upload_action.button("Upload data", key="upload_data", type="primary", on_click=request_input_scroll)
            demo_action.button("Try demo case", key="try_demo_case", on_click=load_demo_inputs)
        with hero_art:
            hero_area = st.container()
    workflow()
    st.markdown('<div id="try-it-section" class="so-section-anchor"></div>', unsafe_allow_html=True)
    input_card = st.container(border=True, key="input_card")
    with input_card:
        st.subheader("Start with a claim. Leave with evidence.")
        upload_panel, claim_panel = st.columns(2, gap="large")
        with upload_panel:
            uploaded = st.file_uploader("1. Upload CSV", type=["csv"],
                                        key=f"csv_upload_{st.session_state.get('upload_widget_version', 0)}",
                                        on_change=use_uploaded_csv)
    if st.session_state.get("demo_mode"):
        uploaded = io.BytesIO((Path(__file__).resolve().parent / "data" / "synthetic_simpson.csv").read_bytes())
        with upload_panel:
            st.info("Demo loaded — click Analyze claim to uncover the hidden pattern.")
    upload_changed = st.session_state.pop("_upload_changed", False)
    if uploaded is not None:
        payload = uploaded.getvalue()
        set_dataset(st.session_state, payload, preserve_claim=bool(st.session_state.get("demo_mode")))
    elif upload_changed:
        clear_dataset(st.session_state)
        payload = None
    else:
        payload = st.session_state.get("dataset_bytes")
    if "claim_input" not in st.session_state and st.session_state.get("extracted_claim"):
        st.session_state["claim_input"] = st.session_state["extracted_claim"]["original_claim"]
    with claim_panel, st.form("claim_extraction"):
        claim = st.text_area("2. Enter claim", height=110, key="claim_input")
        st.caption("Only the claim text is sent to Nebius for extraction.")
        submitted = st.form_submit_button("Analyze claim", type="primary", disabled=payload is None)
    sync_claim(st.session_state, claim)
    if payload is None:
        with hero_area:
            hero_visual()
        progress()
        st.info("Upload a CSV to get started.")
        return
    try:
        data = pd.read_csv(io.BytesIO(payload))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError, ValueError):
        with hero_area:
            hero_visual(has_dataset=True)
        st.error("Could not read this CSV. Upload a valid UTF-8 CSV with column headers.")
        return

    profile = profile_dataset(data)
    with upload_panel:
        st.caption(f"{profile['row_count']:,} rows | {profile['column_count']} columns")
        with st.expander("Preview dataset", expanded=False):
            st.dataframe(data.head(20), hide_index=True)
            st.write("Column profile")
            st.dataframe(profile["columns"], hide_index=True)

    if submitted and "extracted_claim" not in st.session_state:
        if not claim.strip():
            st.warning("Enter a business claim first.")
            return
        try:
            with st.spinner("Extracting claim…"):
                extracted = extract_claim(claim)
        except ClaimExtractionError as exc:
            st.error(str(exc))
        else:
            st.session_state["extracted_claim"] = extracted
    progress_area = st.container()
    if "extracted_claim" in st.session_state:
        mapping = show_schema_mapping(data, st.session_state["extracted_claim"])
        mapping_area = st.container()
        show_audit(data, st.session_state["extracted_claim"])
        if mapping:
            with mapping_area:
                mapping_summary(mapping, st.session_state.get("audit_mapping"), st.session_state.get("audit_result"))
    with progress_area:
        progress(st.session_state.get("audit_result"), st.session_state.get("investigation_result"),
                 st.session_state.get("critic_result"), extracted=st.session_state.get("extracted_claim"),
                 mapping=st.session_state.get("audit_mapping"), verdict=st.session_state.get("verdict_result"))
    with hero_area:
        hero_visual(st.session_state.get("audit_result"), st.session_state.get("investigation_result"), has_dataset=True)


def main():
    st.set_page_config(page_title="Second Opinion", layout="wide")
    apply_theme()
    navigation()
    page_body()
    target = st.session_state.pop("_pending_scroll_target", None)
    input_scroll = st.session_state.pop("_demo_scroll_pending", False)
    if target:
        if target == "final-verdict-result-section":
            if st.session_state.get("verdict_result"):
                scroll_to_section(target)
        elif target != "stress-test-section" or successful_investigation(st.session_state.get("investigation_result")):
            scroll_to_section(target)
    elif input_scroll:
        scroll_to_inputs()
    information_sections()


if __name__ == "__main__":
    main()
