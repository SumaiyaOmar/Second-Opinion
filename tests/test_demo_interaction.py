"""Demo reset and current navigation/hero interaction regressions."""

import hashlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
DEMO = (ROOT / "data/synthetic_simpson.csv").read_bytes()


class DemoInteractionTests(unittest.TestCase):
    def test_demo_click_overrides_previous_upload_and_waits_for_analyze(self):
        previous = b"unrelated,value\nold,123\n"
        with patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(previous)), \
             patch("app.extract_claim") as extract, patch("app.map_schema") as mapper, \
             patch("app.audit_claim") as audit, patch("app.investigate_segments") as investigate, \
             patch("app.run_critic") as critic, patch("app.generate_verdict") as verdict:
            app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
            self.assertEqual(app.session_state["dataset_id"], hashlib.sha256(previous).hexdigest())
            button = app.button(key="try_demo_case")
            self.assertFalse(button.disabled)
            self.assertFalse(button.proto.help)
            # Reproduce a user who already has an upload and completed analysis.
            for name in ("extracted_claim", "schema_mapping_result", "audit_result", "investigation_result",
                         "critic_result", "verdict_result"):
                app.session_state[name] = {"old": True}
            button.click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["dataset_id"], hashlib.sha256(DEMO).hexdigest())
            self.assertEqual(app.text_area[0].value, "The overall score increased after the change.")
            self.assertTrue(app.session_state["suggest_schema_mapping"])
            self.assertFalse(next(b for b in app.button if b.label == "Analyze claim").disabled)
            self.assertEqual(app.session_state["upload_widget_version"], 1)
            for stage in (extract, mapper, audit, investigate, critic, verdict):
                stage.assert_not_called()
            app.run(timeout=30)
            self.assertEqual(app.session_state["dataset_id"], hashlib.sha256(DEMO).hexdigest())
            app.button(key="try_demo_case").click().run(timeout=30)
            self.assertFalse(app.exception)
            extract.assert_not_called()
            mapper.assert_not_called()

    def test_fresh_demo_click_and_upload_anchor_with_full_chrome(self):
        with patch("app.extract_claim") as extract:
            app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
            before = next(n.value for n in app.markdown if '<div class="so-hero-scene">' in n.value)
            app.button(key="try_demo_case").click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["dataset_id"], hashlib.sha256(DEMO).hexdigest())
        self.assertEqual(app.text_area[0].value, "The overall score increased after the change.")
        extract.assert_not_called()
        self.assertFalse(any(n.label == "Upload data" for n in app.get("link_button")))
        self.assertFalse(app.button(key="upload_data").disabled)
        html = " ".join(n.value for n in app.markdown)
        after = next(n.value for n in app.markdown if '<div class="so-hero-scene">' in n.value)
        self.assertEqual(before, after)
        self.assertIn('74<small>↑ from 36', after)
        self.assertIn('WAIT A SECOND ↗', after)
        self.assertNotIn('baseline —', after)
        self.assertNotIn('Awaiting investigation', after)
        self.assertNotIn('Your evidence will appear here', after)
        self.assertTrue(any(n.value == "Demo loaded — click Analyze claim to uncover the hidden pattern." for n in app.info))
        self.assertIn('id="try-it-section"', html)
        self.assertIn('aria-label="Main navigation"', html)
        css = (ROOT / "ui/theme.css").read_text()
        self.assertIn('.so-hero-scene { pointer-events: none; }', css)
        self.assertIn('.so-navbar { pointer-events: auto; }', css)
        self.assertIn('z-index: 100; pointer-events: none;', css)

    def test_selecting_a_new_upload_exits_demo_mode(self):
        app = AppTest.from_string('''import streamlit as st
from app import use_uploaded_csv
st.session_state["demo_mode"] = True
use_uploaded_csv()
st.write(st.session_state["demo_mode"])
''').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["demo_mode"])

    def test_loaded_or_incomplete_audit_keeps_illustration(self):
        for audit in (None, {}, {"computed_values": {}}, {"computed_values": {"left": 19}},
                      {"computed_values": {"left": float("nan"), "right": 12}}):
            with self.subTest(audit=audit):
                with patch("ui.story.st.markdown") as render:
                    from ui.story import hero_visual
                    hero_visual(audit, has_dataset=True)
                html = render.call_args.args[0]
                self.assertIn('74<small>↑ from 36', html)
                self.assertIn('Illustrative demo', html)
                self.assertNotIn('baseline —', html)

    def test_live_hero_never_mixes_demo_values_with_real_segments(self):
        from ui.story import hero_visual
        with patch("ui.story.st.markdown") as render:
            hero_visual({"computed_values": {"left": 19, "right": 12}},
                        {"segment_results": [{"segment": "Actual group", "left": 7, "right": 9}]},
                        has_dataset=True)
        html = render.call_args.args[0]
        self.assertIn('19<small>baseline 12', html)
        self.assertIn('Actual group', html)
        self.assertNotIn('Illustrative demo', html)
        self.assertNotIn('↑ from 36', html)
        self.assertNotIn('HIGH ↘', html)


if __name__ == "__main__":
    unittest.main()
