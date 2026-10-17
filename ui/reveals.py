"""Render already-calculated evidence as cards; no analytical decisions."""

from html import escape
import math

import streamlit as st


def text(value):
    return escape(str(value), quote=True)


def number(value, percent=False):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "Not available"
    return format(value, ".0%" if percent else ",.6g")


def progress(audit=None, investigation=None, critic=None, *, extracted=None, mapping=None, verdict=None):
    items = [
        ("Claim interpreted", bool(extracted)),
        ("Mapping confirmed", bool(mapping and mapping.get("confirmed"))),
        ("Numbers checked", bool(audit and audit.get("calculation") and audit.get("computed_values"))),
        ("Hidden pattern checked", bool((investigation or {}).get("computational_receipt", {}).get("executed"))),
        ("Stress tested", bool(critic and critic.get("checks_run"))),
        ("Verdict ready", bool(verdict)),
    ]
    pills = ''.join(f'<span class="so-stage-pill {"complete" if done else "pending"}">'
                    f'<i></i>{text(title)}<small>{"Complete" if done else "Pending"}</small></span>' for title, done in items)
    segments = ''.join(f'<span class="{"complete" if done else "pending"}"></span>' for _, done in items)
    st.markdown('<section class="so-progress-box" aria-label="Analysis progress">'
                f'<div class="so-stage-pills">{pills}</div><div class="so-stage-line">{segments}</div></section>',
                unsafe_allow_html=True)


def result_reveals(audit, investigation):
    values = (audit or {}).get("computed_values") or {}
    if not all(isinstance(values.get(side), (int, float)) and not isinstance(values[side], bool)
               and math.isfinite(values[side]) for side in ("right", "left")):
        return
    reversal = (investigation or {}).get("finding") == "direction_reversal"
    headline = ('<article class="so-reveal pale-blue"><span class="so-eyebrow">The headline</span>'
                f'<div class="so-number">{number(values["right"])} → {number(values["left"])}</div>'
                f'<h3>{"Looks like improvement." if reversal and values["left"] > values["right"] else "The aggregate comparison."}</h3>'
                f'<small>{text(audit.get("metric", "Metric"))} · Baseline → comparison.</small></article>')
    contradiction = ""
    if reversal:
        segments = investigation.get("segment_results") or []
        heading = ("But every segment declined." if segments and all(
            isinstance(row.get("change"), (int, float)) and row["change"] < 0 for row in segments)
            else "But the segment trends run the other way.")
        contradiction = ('<article class="so-reveal pale-coral"><span class="so-eyebrow">Under the surface</span>'
                         f'<h3>{heading}</h3>' + ''.join(
                             f'<div class="so-segment"><span>{text(row["segment"])}</span>'
                             f'<strong>{number(row.get("right"))} → {number(row.get("left"))}</strong></div>'
                             for row in segments) + '</article>')
    elif investigation:
        explanation = (investigation.get("mix_shift_evidence") or {}).get("explanation")
        contradiction = ('<article class="so-reveal pale-coral"><span class="so-eyebrow">Under the surface</span>'
                         f'<h3>Check the segment evidence.</h3><p>{text(explanation or "See the investigation details for the available evidence.")}</p></article>')
    st.markdown('<div class="so-reveal-pair">' + headline + contradiction + '</div>', unsafe_allow_html=True)
    if investigation:
        from ui.story import segment_cards, composition_section
        segment_cards(investigation)
        if investigation.get("finding") in {"direction_reversal", "mix_shift"}:
            composition_section(investigation, audit)


def evidence_cards(result, audit, investigation, critic, mapping=None):
    from ui.audit_summary import audit_summary
    mix = (investigation or {}).get("mix_shift_evidence") or {}
    supported = result.get("what_is_supported") or []
    unsupported = result.get("what_is_not_supported") or []
    items = [
        ("What changed", audit_summary(audit, mapping)),
        ("What contradicts it", unsupported[0] if unsupported else "No contradiction was identified in the available checks."),
        ("Why it happened", mix.get("explanation") or "The available comparison does not establish a cause."),
        ("Stability", critic["stability_summary"] if critic else "Stress tests have not been run."),
    ]
    st.markdown('<div class="so-evidence-grid">' + ''.join(
        f'<article class="so-evidence-card"><h4>{text(title)}</h4><p>{text(body)}</p></article>'
        for title, body in items) + '</div>', unsafe_allow_html=True)
