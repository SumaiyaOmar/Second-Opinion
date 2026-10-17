"""Durable uploads and dependency-aware navigation/stage state."""

import copy
import io
import unittest
from unittest.mock import patch

from core.verdict import generate_verdict
from test_analysis_flow_ux import audited_app
from test_ui_presentation import CLAIM, MAPPING, PAYLOAD
from ui.session import set_dataset, sync_claim, store_audit


class SessionDependencyTests(unittest.TestCase):
    def test_reused_upload_stream_survives_investigation_critic_and_verdict(self):
        shared = io.BytesIO(PAYLOAD)
        shared.seek(len(PAYLOAD))  # Previously produced EmptyDataError on rerun.
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=shared), \
             patch("app.generate_verdict", side_effect=lambda *a, **kw: generate_verdict(*a, use_model=False)):
            app = audited_app().run(timeout=30)
            self.assertFalse(app.error)
            upstream = {key: copy.deepcopy(app.session_state[key]) for key in
                        ("dataset_id", "claim_input", "extracted_claim", "audit_mapping", "audit_result")}
            next(s for s in app.selectbox if s.label == "Segment column for breakdown").select("segment")
            app.checkbox(key="_investigation_confirmed_widget").check()
            next(b for b in app.button if b.label == "Investigate hidden pattern").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["investigation_result"]["finding"], "direction_reversal")
            investigation = copy.deepcopy(app.session_state["investigation_result"])
            for key, value in upstream.items():
                self.assertEqual(app.session_state[key], value, key)
            self.assertEqual(app.session_state["dataset_bytes"], PAYLOAD)
            app.run()
            self.assertEqual(app.session_state["investigation_result"], investigation)
            self.assertEqual(app.selectbox(key="_investigation_segment_widget").value, "segment")
            next(b for b in app.button if b.label == "Run stress tests").click().run()
            critic = copy.deepcopy(app.session_state["critic_result"])
            self.assertEqual(app.session_state["investigation_result"], investigation)
            next(b for b in app.button if b.label == "Generate final verdict").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["critic_result"], critic)
            self.assertEqual(app.session_state["investigation_result"], investigation)
            for key, value in upstream.items():
                self.assertEqual(app.session_state[key], value, key)
            app.run()
            self.assertIn("verdict_result", app.session_state)

    def test_upload_cta_is_a_same_session_scroll_action(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.scroll_to_inputs") as scroll:
            app = audited_app().run(timeout=30)
            before = copy.deepcopy(app.session_state["audit_result"])
            self.assertFalse(any(b.label == "Upload data" for b in app.get("link_button")))
            app.button(key="upload_data").click().run()
            self.assertFalse(app.exception)
            scroll.assert_called_once()
            self.assertEqual(app.session_state["audit_result"], before)
            self.assertEqual(app.session_state["claim_input"], CLAIM["original_claim"])
            app.run()
            scroll.assert_called_once()

    def test_only_real_dependency_changes_invalidate_results(self):
        state = {}
        set_dataset(state, PAYLOAD)
        state.update(claim_input="Claim A", extracted_claim={"original_claim":"Claim A"})
        sync_claim(state, "Claim A")
        store_audit(state, MAPPING, {"status":"Supported"})
        state.update(investigation_result={"finding":"direction_reversal"}, critic_result={"test":1}, verdict_result={"test":2})
        before = copy.deepcopy(state)
        set_dataset(state, PAYLOAD)
        sync_claim(state, "Claim A")
        store_audit(state, MAPPING, {"status":"Supported"})
        self.assertEqual(state, before)
        store_audit(state, {**MAPPING,"operator":"less"}, {"status":"Unsupported"})
        self.assertIn("extracted_claim", state)
        self.assertNotIn("investigation_result", state)
        self.assertNotIn("critic_result", state)
        self.assertNotIn("verdict_result", state)
        sync_claim(state, "Claim B")
        self.assertIn("dataset_bytes", state)
        self.assertNotIn("extracted_claim", state)
        self.assertNotIn("audit_mapping", state)
        self.assertNotIn("audit_result", state)
        state.update(claim_input="Claim B", extracted_claim={"original_claim":"Claim B"})
        set_dataset(state, b"new_column\n123\n")
        self.assertNotIn("claim_input", state)
        self.assertNotIn("extracted_claim", state)

    def test_missing_widget_value_on_unrelated_rerun_keeps_owned_bytes(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)) as upload:
            app = audited_app().run(timeout=30)
            before = copy.deepcopy(app.session_state["audit_result"])
            upload.return_value = None
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["audit_result"], before)
            self.assertTrue(any(b.label == "Investigate hidden pattern" for b in app.button))

    def test_explicit_upload_removal_clears_downstream_state(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)) as upload:
            app = audited_app().run(timeout=30)
            upload.return_value = None
            app.session_state["_upload_changed"] = True
            app.run()
            self.assertFalse(app.exception)
            for key in ("dataset_bytes", "dataset_id", "extracted_claim", "audit_mapping", "audit_result"):
                self.assertNotIn(key, app.session_state)

    def test_analyze_same_claim_does_not_reextract_or_clear_audit(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.extract_claim") as extract:
            app = audited_app().run(timeout=30)
            before = copy.deepcopy(app.session_state["audit_result"])
            next(b for b in app.button if b.label == "Analyze claim").click().run()
            self.assertFalse(app.exception)
            extract.assert_not_called()
            self.assertEqual(app.session_state["audit_result"], before)


if __name__ == "__main__":
    unittest.main()
