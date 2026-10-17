"""Small reusable Streamlit evidence components."""

import streamlit as st
from copy import deepcopy


def show_chart(chart, kind=None):
    if chart is None:
        st.caption("Chart unavailable: this calculation is missing or not applicable.")
        return
    # Style a copy: all data and encodings still come from deterministic helpers.
    styled = deepcopy(chart)
    styled["height"] = 210
    styled["background"] = "#ffffff"
    styled["config"] = {
        "view": {"stroke": None},
        "axis": {"labelColor": "#53607a", "titleColor": "#17213d", "gridColor": "#edf0f8"},
        "legend": {"labelColor": "#17213d", "orient": "bottom"},
        "title": {"color": "#17213d", "fontSize": 14, "anchor": "start"},
        "font": "Segoe UI",
    }
    if "color" in styled.get("encoding", {}):
        styled["encoding"]["color"]["scale"] = {"range": ["#3049ee", "#ff6b57"]}
    if kind == "aggregate":
        styled["encoding"].pop("xOffset", None)
        styled["encoding"]["x"] = {"field": "series", "type": "nominal", "sort": None, "title": None}
        styled["encoding"]["color"]["scale"] = {"range": ["#9aacf5", "#3049ee"]}
        styled["encoding"]["color"]["legend"] = None
        styled["mark"] = {"type": "bar", "cornerRadiusTopLeft": 7, "cornerRadiusTopRight": 7, "width": 42, "tooltip": True}
    elif kind == "segments":
        styled["encoding"].pop("xOffset", None)
        styled["encoding"]["x"] = {"field": "series", "type": "nominal", "sort": None, "title": None}
        styled["encoding"]["color"] = {"field": "category", "type": "nominal", "title": None,
                                         "sort": None, "scale": {"range": ["#fa6856", "#c52988", "#087f7a", "#3049ee"]}}
        styled["mark"] = {"type": "line", "point": {"filled": True, "size": 85}, "strokeWidth": 2, "tooltip": True}
    elif kind == "composition":
        styled["encoding"].pop("xOffset", None)
        styled["encoding"]["x"] = {"field": "value", "type": "quantitative", "stack": "zero", "title": None,
                                    "scale": {"domain": [0, 1]}, "axis": {"format": ".0%"}}
        styled["encoding"]["y"] = {"field": "series", "type": "nominal", "sort": None, "title": None}
        styled["encoding"]["color"] = {"field": "category", "type": "nominal", "title": None,
                                         "sort": None, "scale": {"range": ["#087f7a", "#f8cc46", "#c52988", "#3049ee", "#fa6856"]}}
        styled["mark"] = {"type": "bar", "height": 38, "tooltip": True}
    st.vega_lite_chart(spec=styled, width="stretch", theme=None)
    st.caption("Calculated from the confirmed comparison. An increase does not necessarily mean business improvement.")


def show_proof(receipt, label="Show proof"):
    with st.expander(label, expanded=False):
        st.json(receipt)
