"""Durable confirmation ownership and success-only scroll sequencing."""

import copy
import io
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim
from test_analysis_flow_ux import audited_app
from test_ui_presentation import PAYLOAD, CLAIM, MAPPING


class InvestigationStateScrollTests(unittest.TestCase):
    def test_conditional_widget_cleanup_cannot_delete_confirmation(self):
        app = AppTest.from_string('''import streamlit as st
from ui.investigation_form_state import initialize_investigation, persist_investigation_inputs, SEGMENT_WIDGET, CONFIRMED_WIDGET
if not st.session_state.get("hide_stage"):
    initialize_investigation(st.session_state, "segment")
    st.selectbox("Segment", ["segment"], index=None, key=SEGMENT_WIDGET,
                 on_change=persist_investigation_inputs, args=(st.session_state,))
    st.checkbox("Confirmed", key=CONFIRMED_WIDGET,
                on_change=persist_investigation_inputs, args=(st.session_state,))
''').run()
        app.checkbox(key="_investigation_confirmed_widget").check().run()
        self.assertTrue(app.session_state["investigation_confirmed"])
        app.session_state["hide_stage"] = True
        app.run()
        self.assertTrue(app.session_state["investigation_confirmed"])
        self.assertEqual(app.session_state["investigation_segment"], "segment")
        self.assertNotIn("_investigation_confirmed_widget", app.session_state)
        app.session_state["hide_stage"] = False
        app.run()
        self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)

    def test_invalid_confirmation_does_not_call_investigator_or_scroll(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.investigate_segments") as investigator, patch("app.scroll_to_section") as scroll:
            app = audited_app(demo=True).run(timeout=30)
            app.button(key="run_investigation").click().run()
            self.assertFalse(app.exception)
            investigator.assert_not_called()
            scroll.assert_not_called()
            self.assertFalse(app.session_state["investigation_confirmed"])
            self.assertNotIn("_pending_scroll_target", app.session_state)
            self.assertTrue(any("confirm the segment" in w.value for w in app.warning))

    def test_real_inconclusive_result_is_stored_without_any_scroll(self):
        data = pd.read_csv(io.BytesIO(PAYLOAD))
        data["segment"] = "only group"
        payload = data.to_csv(index=False).encode()
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(payload)), \
             patch("app.scroll_to_section") as scroll:
            app = audited_app().run(timeout=30)
            # The new input correctly invalidates the seeded audit; explicitly
            # provide its current deterministic audit before continuing.
            app.session_state["claim_input"] = CLAIM["original_claim"]
            app.session_state["_claim_snapshot"] = CLAIM["original_claim"]
            app.session_state["extracted_claim"] = CLAIM
            app.session_state["audit_mapping"] = MAPPING
            app.session_state["audit_result"] = audit_claim(data, CLAIM, MAPPING)
            app.run()
            app.selectbox(key="_investigation_segment_widget").select("segment")
            app.checkbox(key="_investigation_confirmed_widget").check().run()
            app.button(key="run_investigation").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["investigation_result"]["finding"], "inconclusive")
            self.assertTrue(app.session_state["investigation_confirmed"])
            scroll.assert_not_called()
            app.run()
            scroll.assert_not_called()

    def test_success_scroll_dispatch_sees_stored_result_and_is_consumed(self):
        dispatched = []
        import streamlit as st
        def observe(target):
            self.assertTrue(st.session_state["investigation_confirmed"])
            self.assertEqual(st.session_state["investigation_request"]["segment_column"], "segment")
            self.assertTrue(st.session_state["investigation_request"]["segment_confirmed"])
            self.assertEqual(st.session_state["investigation_result"]["finding"], "direction_reversal")
            dispatched.append(target)
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.scroll_to_section", side_effect=observe):
            app = audited_app(demo=True).run(timeout=30)
            audit = copy.deepcopy(app.session_state["audit_result"])
            app.checkbox(key="_investigation_confirmed_widget").check().run()
            app.button(key="run_investigation").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(dispatched, ["stress-test-section"])
            self.assertEqual(app.session_state["audit_result"], audit)
            self.assertTrue(app.checkbox(key="_investigation_confirmed_widget").value)
            self.assertEqual([(r["right"], r["left"]) for r in app.session_state["investigation_result"]["segment_results"]], [(90,80),(30,20)])
            self.assertNotIn("_pending_scroll_target", app.session_state)
            app.run()
            self.assertEqual(dispatched, ["stress-test-section"])


if __name__ == "__main__":
    unittest.main()
