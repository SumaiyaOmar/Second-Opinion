"""Light-card text contrast and unchanged form interaction checks."""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


CSS = (Path(__file__).resolve().parents[1] / "ui/theme.css").read_text(encoding="utf-8")


def contrast(foreground, background):
    def luminance(hex_color):
        channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
    first, second = sorted((luminance(foreground), luminance(background)))
    return (second + .05) / (first + .05)


class FormContrastTests(unittest.TestCase):
    def test_label_caption_placeholder_and_disabled_styles_are_explicit(self):
        for selector in ('[data-testid="stWidgetLabel"] p', '[data-testid="stCheckbox"] label p',
                         '[data-testid="stToggle"] label p', '[data-testid="stCaptionContainer"] p',
                         'input::placeholder', 'textarea::placeholder', 'input:disabled',
                         '[role="option"][aria-selected="true"]'):
            self.assertIn(selector, CSS)
        self.assertIn('color: #17213d !important', CSS)
        self.assertIn('-webkit-text-fill-color: #53607a !important', CSS)
        self.assertIn('background-color: #edf0f5 !important', CSS)

    def test_chosen_text_surface_pairs_meet_normal_text_contrast(self):
        for foreground, background in (('#17213d', '#ffffff'), ('#53607a', '#ffffff'),
                                      ('#53607a', '#f2f5fc'), ('#58647a', '#edf0f5'),
                                      ('#493508', '#fff2c9'), ('#172d63', '#eaf0ff')):
            with self.subTest(foreground=foreground, background=background):
                self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_native_controls_remain_enabled_and_operable(self):
        app = AppTest.from_string('''import streamlit as st
from ui.style import apply_theme
apply_theme()
with st.form("contrast_test"):
    st.selectbox("Metric", ["score", "revenue"])
    st.text_input("Compare", placeholder="Choose a bucket")
    st.checkbox("I confirm the mapping")
    st.caption("Review columns and buckets before running the audit.")
    st.form_submit_button("Run deterministic audit")
''').run()
        app.selectbox[0].select("revenue")
        app.text_input[0].set_value("after")
        app.checkbox[0].check()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "revenue")
        self.assertEqual(app.text_input[0].value, "after")
        self.assertTrue(app.checkbox[0].value)


if __name__ == "__main__":
    unittest.main()
