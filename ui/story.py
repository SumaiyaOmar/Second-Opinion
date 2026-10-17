"""Screenshot-led story components using existing output values only."""

import math

import streamlit as st

from ui.reveals import text, number


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def hero_visual(audit=None, investigation=None, has_dataset=False):
    values = (audit or {}).get("computed_values") or {}
    live = all(finite(values.get(k)) for k in ("left", "right"))
    # Loading inputs is not evidence. Keep the illustration until an actual
    # finite aggregate comparison exists, regardless of dataset/demo state.
    illustrative = not live
    current = number(values["left"]) if live else "74" if illustrative else "—"
    baseline = number(values["right"]) if live else "36" if illustrative else "—"
    rows = ((investigation or {}).get("segment_results") or []) if live else []
    captions = [text(r["segment"]) for r in rows[:2]]
    if not captions:
        captions = ["HIGH ↘", "LOW ↘"] if illustrative else ["Segment evidence", "Awaiting investigation"]
    headline_width = (abs(values["left"]) / (max(abs(values["left"]), abs(values["right"])) or 1) * 100
                      if live else 74 if illustrative else 0)
    widths = [abs(r["left"]) for r in rows[:2] if finite(r.get("left"))]
    scale = max(widths) if widths and max(widths) else 1
    widths = [v / scale * 100 for v in widths] if widths else [80, 20] if illustrative else [0, 0]
    caption = "Illustrative demo · not your analysis" if illustrative else "From the current audit" if live else "Your evidence will appear here"
    st.markdown(
        '<div class="so-hero-scene"><div class="so-curve"></div><div class="so-grid-paper">'
        '<div class="so-floating-headline"><div class="so-tiny-label">THE HEADLINE <i></i></div>'
        f'<div class="so-hero-value">{current}<small>{"↑ from" if illustrative else "baseline"} {baseline}</small></div>'
        f'<div class="so-hero-track"><span style="width:{headline_width:.4f}%"></span></div></div>'
        '<div class="so-sticker">WAIT A SECOND ↗</div>'
        '<div class="so-floating-segments"><div class="so-tiny-label">UNDER THE SURFACE</div>'
        '<div class="so-mini-columns">' + ''.join(
            f'<div><b>{segment_label}</b><div class="so-mini-track"><span class="tone-{i}" '
            f'style="width:{widths[i] if i < len(widths) else 0:.4f}%"></span></div></div>'
            for i, segment_label in enumerate(captions)) + '</div></div></div>'
        f'<p class="so-scene-caption">{text(caption)}</p></div>', unsafe_allow_html=True)


def segment_cards(investigation):
    rows = (investigation or {}).get("segment_results") or []
    if not rows:
        return
    values = [r.get(side) for r in rows for side in ("right", "left")]
    if not all(finite(v) for v in values):
        return
    # Normalization affects visual bar lengths only; all labels are upstream values.
    scale = max(abs(v) for v in values) or 1
    cards = []
    for i, row in enumerate(rows):
        bars = ''.join(
            f'<div class="so-bar-row"><span>{number(row[side])}</span><div class="so-bar-rail">'
            f'<div class="so-segment-bar {"muted" if side == "left" else ""}" '
            f'style="width:{abs(row[side])/scale*100:.4f}%"></div></div>'
            f'<small>{"Baseline" if side == "right" else "Comparison"}</small></div>'
            for side in ("right", "left"))
        cards.append(f'<article class="so-horizontal-segment tone-{i % 2}"><h4>{text(row["segment"])}</h4>{bars}</article>')
    st.markdown('<div class="so-segment-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def composition_section(investigation, audit):
    rows = (investigation or {}).get("segment_weights") or []
    if not rows or not all(finite(r.get(f"{side}_share")) and 0 <= r[f"{side}_share"] <= 1
                           for r in rows for side in ("right", "left")):
        return
    comparison = (audit or {}).get("comparison") or {}
    bars = []
    for side, title in (("right", "BEFORE"), ("left", "AFTER")):
        shares = ''.join(f'<span class="so-share-color-{i % 5}" style="width:{r[f"{side}_share"]*100:.5f}%" '
                         f'title="{text(r["segment"])}: {number(r[f"{side}_share"], True)}"></span>'
                         for i, r in enumerate(rows))
        labels = ' · '.join(f'{number(r[f"{side}_share"], True)} {text(r["segment"])}' for r in rows)
        bars.append(f'<div class="so-share-label"><b>{title} <small>{text(comparison.get(side, ""))}</small></b></div>'
                    f'<div class="so-share-stack" role="img" aria-label="{title}: {labels}">{shares}</div>'
                    f'<p class="so-share-values">{labels}</p>')
    legend = ''.join(f'<span><i class="so-share-color-{i % 5}"></i>{text(r["segment"])}</span>' for i, r in enumerate(rows))
    st.markdown('<section class="so-mint-section"><div class="so-composition-copy"><span class="so-eyebrow">The composition shift</span>'
                '<h3>Something doesn’t add up.</h3><p>The mix of observations changed. '
                'Compare the shares alongside the segment results; this does not establish a cause.</p></div>'
                '<div class="so-composition-card">' + ''.join(bars) + '<div class="so-legend">' + legend + '</div></div></section>',
                unsafe_allow_html=True)
