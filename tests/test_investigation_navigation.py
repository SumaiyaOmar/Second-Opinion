"""One-shot navigation from investigation to the live stress-test stage."""

import copy
import io
import re
import unittest
from unittest.mock import patch

from test_analysis_flow_ux import audited_app
from test_ui_presentation import PAYLOAD


class InvestigationNavigationTests(unittest.TestCase):
    def test_post_investigation_scroll_targets_stress_and_fires_once(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.scroll_to_section") as scroll, patch("app.scroll_to_inputs") as inputs:
            app = audited_app().run(timeout=30)
            audit = copy.deepcopy(app.session_state["audit_result"])
            next(s for s in app.selectbox if s.label == "Segment column for breakdown").select("segment")
            app.checkbox(key="_investigation_confirmed_widget").check()
            next(b for b in app.button if b.label == "Investigate hidden pattern").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["investigation_result"]["finding"], "direction_reversal")
            self.assertEqual(app.session_state["audit_result"], audit)
            self.assertEqual(app.selectbox(key="_investigation_segment_widget").value, "segment")
            self.assertTrue(any('id="stress-test-section"' in n.value for n in app.markdown))
            scroll.assert_called_once_with("stress-test-section")
            inputs.assert_not_called()
            self.assertNotIn("_pending_scroll_target", app.session_state)
            self.assertNotIn("_demo_scroll_pending", app.session_state)
            html = " ".join(n.value for n in app.markdown)
            self.assertIn('href="#benchmark-evidence-section" target="_self">Evidence', html)
            self.assertNotIn('id="evidence"', html)
            ids = re.findall(r'\bid="([^"]+)"', html)
            ids += [h.proto.anchor for h in app.subheader if h.proto.anchor]
            self.assertEqual(len(ids), len(set(ids)))
            app.run()
            scroll.assert_called_once_with("stress-test-section")
            self.assertEqual(app.session_state["audit_result"], audit)
            self.assertIn("investigation_result", app.session_state)

    def test_scroller_uses_only_named_target_and_cancels_old_requests(self):
        from ui.interactions import scroll_to_section
        with patch("ui.interactions.components.html") as render:
            scroll_to_section("stress-test-section")
        script = render.call_args.args[0]
        self.assertIn('const targetId = "stress-test-section";', script)
        self.assertIn('getElementById(targetId)', script)
        self.assertIn('host.__secondOpinionScrollToken !== requestToken', script)
        self.assertIn('host.history.replaceState', script)
        self.assertNotIn('"benchmark-evidence-section"', script)
        self.assertNotIn('__TARGET_ID__', script)
        self.assertEqual(render.call_args.kwargs["tab_index"], -1)

    def test_confirmation_survives_rerun_and_persisted_request_drives_demo(self):
        import streamlit as st
        from core.investigator import investigate_segments
        requests = []
        def observe(data, claim, audit, mapping, **kwargs):
            request = copy.deepcopy(st.session_state["investigation_request"])
            self.assertTrue(request["segment_confirmed"])
            self.assertEqual(request["segment_column"], "segment")
            self.assertTrue(kwargs["segment_confirmed"])
            self.assertEqual(kwargs["segment_column"], "segment")
            self.assertEqual(request["audit_result"], audit)
            requests.append(request)
            return investigate_segments(data, claim, audit, mapping, **kwargs)
        def scroll_marker(target):
            st.markdown(f'<div id="test-scroll-dispatch">{target}</div>', unsafe_allow_html=True)
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.investigate_segments", side_effect=observe), patch("app.scroll_to_section", side_effect=scroll_marker) as scroll, \
             patch("app.scroll_to_inputs"):
            app = audited_app(demo=True).run(timeout=30)
            self.assertEqual(app.selectbox(key="_investigation_segment_widget").value, "segment")
            app.checkbox(key="_investigation_confirmed_widget").check().run()
            app.run()
            self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)
            audit = copy.deepcopy(app.session_state["audit_result"])
            app.button(key="upload_data").click().run()
            self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)
            app.button(key="run_investigation").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)
            self.assertEqual(app.session_state["investigation_segment"], "segment")
            self.assertEqual(app.session_state["audit_result"], audit)
            result = app.session_state["investigation_result"]
            self.assertEqual(result["finding"], "direction_reversal")
            self.assertEqual([audit["computed_values"][side] for side in ("right", "left")], [36, 74])
            self.assertEqual([(r["right"], r["left"]) for r in result["segment_results"]], [(90,80),(30,20)])
            self.assertEqual(len(requests), 1)
            scroll.assert_called_once_with("stress-test-section")
            html = " ".join(n.value for n in app.markdown)
            self.assertLess(html.index('id="test-scroll-dispatch"'), html.index('id="benchmark-evidence-section"'))
            self.assertIn('href="#benchmark-evidence-section" target="_self">Evidence', html)
            app.run()
            scroll.assert_called_once()
            self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)
            self.assertEqual(app.session_state["investigation_request"], requests[0])


if __name__ == "__main__":
    unittest.main()
