"""Verdict commits before optional wording and survives normal UI reruns."""

from copy import deepcopy
import io
import unittest
from unittest.mock import patch

from test_ui_presentation import seeded_app, PAYLOAD


class VerdictPersistenceTests(unittest.TestCase):
    def test_demo_model_failure_keeps_committed_verdict_and_upstream_state(self):
        import streamlit as st

        observed = []

        def unavailable():
            # The deterministic verdict must already exist when wording starts.
            observed.append(deepcopy(st.session_state["verdict_result"]))
            raise RuntimeError("private-provider-detail SECRET-DO-NOT-RENDER")

        with patch("app.map_schema", return_value={}), \
             patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("core.verdict.get_nebius_client", side_effect=unavailable), \
             patch("app.scroll_to_section") as scroll:
            app = seeded_app(results=True)
            del app.session_state["verdict_result"]
            app.run(timeout=30)
            upstream = {key: deepcopy(app.session_state[key]) for key in (
                "dataset_bytes", "claim_input", "extracted_claim", "audit_mapping", "audit_result",
                "investigation_result", "critic_result")}
            next(b for b in app.button if b.label == "Generate final verdict").click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(observed), 1)
            self.assertEqual(observed[0]["final_status"], "Partially supported")
            verdict = deepcopy(app.session_state["verdict_result"])
            self.assertEqual(verdict["final_status"], "Partially supported")
            self.assertEqual(verdict["computational_receipts"]["explanation_source"], "deterministic_fallback")
            self.assertTrue(verdict["corrected_conclusion"])
            self.assertTrue(any("Final verdict: Partially supported" == s.value for s in app.subheader))
            self.assertTrue(next(b for b in app.button if b.label == "Generate final verdict").disabled)
            scroll.assert_called_once_with("final-verdict-result-section")
            self.assertNotIn("_pending_scroll_target", app.session_state)
            self.assertEqual(sum('id="final-verdict-result-section"' in n.value for n in app.markdown), 1)
            app.run(timeout=30)
            self.assertEqual(app.session_state["verdict_result"], verdict)
            for key, value in upstream.items():
                self.assertEqual(app.session_state[key], value, key)
            rendered = " ".join(str(n.value) for n in [*app.markdown, *app.info, *app.error])
            self.assertNotIn("SECRET-DO-NOT-RENDER", rendered)
            self.assertNotIn("private-provider-detail", rendered)
            scroll.assert_called_once_with("final-verdict-result-section")
            self.assertEqual(len(observed), 1)

    def test_existing_verdict_does_not_scroll_without_generation(self):
        with patch("app.map_schema", return_value={}), \
             patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.scroll_to_section") as scroll:
            app = seeded_app(results=True).run(timeout=30)
            app.run(timeout=30)
            self.assertFalse(app.exception)
            scroll.assert_not_called()
            self.assertTrue(next(b for b in app.button if b.label == "Generate final verdict").disabled)

    def test_stale_verdict_target_without_result_is_consumed_without_scroll(self):
        with patch("app.map_schema", return_value={}), \
             patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.scroll_to_section") as scroll:
            app = seeded_app(results=True)
            del app.session_state["verdict_result"]
            app.session_state["_pending_scroll_target"] = "final-verdict-result-section"
            app.run(timeout=30)
            self.assertNotIn("_pending_scroll_target", app.session_state)
            scroll.assert_not_called()


if __name__ == "__main__":
    unittest.main()
