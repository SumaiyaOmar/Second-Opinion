"""Local presentation assets. No external font or script requests."""

from pathlib import Path

import streamlit as st


def apply_theme():
    css = Path(__file__).with_name("theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
