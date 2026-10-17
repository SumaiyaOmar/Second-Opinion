"""Persisted comparison form reaches the existing Auditor unchanged."""

import copy
import io
import unittest
from unittest.mock import patch

import streamlit as st

from core.auditor import audit_claim
from core.verdict import generate_verdict
from test_ui_presentation import seeded_app, CLAIM, PAYLOAD


class AuditFormPropagationTests(unittest.TestCase):
    def test_completed_form_survives_defaults_navigation_and_entire_pipeline(self):
        received = []
        def observe(data, claim, mapping=None):
            if mapping is not None:
                snapshot = copy.deepcopy(st.session_state["audit_submission"])
                self.assertEqual(snapshot["request"], mapping)
                self.assertEqual(snapshot["missing_fields"], [])
                received.append(copy.deepcopy(mapping))
            return audit_claim(data, claim, mapping)
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(PAYLOAD)), \
             patch("app.audit_claim", side_effect=observe), patch("app.scroll_to_inputs"), \
             patch("app.generate_verdict", side_effect=lambda *a, **kw: generate_verdict(*a, use_model=False)):
            app = seeded_app().run(timeout=30)
            for label, value in (("Metric","score"), ("Calculation type","two_periods"),
                                 ("Aggregation","mean"), ("Comparison field","period")):
                next(s for s in app.selectbox if s.label == label).select(value)
            next(s for s in app.selectbox if s.label.startswith("Claimed relationship")).select("greater")
            next(s for s in app.text_input if s.label == "Compare").set_value("after")
            next(s for s in app.text_input if s.label == "Baseline").set_value("before")
            next(c for c in app.checkbox if c.label.startswith("I confirm these columns")).check()
            app.run()
            # A later proposal changes the default; it must not overwrite edits.
            app.session_state["schema_mapping_result"] = dict(metric_column="score", time_column="period",
                aggregation="sum", comparison_bucket="after", baseline_bucket="before", needs_confirmation=True,
                confirmation_fields=["baseline_bucket", "comparison_bucket"],
                field_validity={"baseline_bucket": {"status": "ambiguous"},
                                "comparison_bucket": {"status": "ambiguous"}})
            app.run()
            self.assertTrue(any("Please confirm: Baseline, Compare" in n.value for n in app.warning))
            app.button(key="upload_data").click().run()
            self.assertEqual(next(s for s in app.selectbox if s.label == "Aggregation").value, "mean")
            self.assertEqual(next(s for s in app.selectbox if s.label.startswith("Claimed relationship")).value, "greater")
            self.assertEqual(received, [])
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            self.assertFalse(app.exception)
            expected = dict(confirmed=True, metric="score", calculation_type="two_periods", aggregation="mean",
                            operator="greater", group_column="period", left="after", right="before", target=None, target_kind="absolute")
            self.assertEqual(received, [expected])
            self.assertEqual(app.session_state["audit_mapping"], expected)
            audit = app.session_state["audit_result"]
            self.assertEqual(audit["status"], "Supported")
            self.assertEqual(audit["computed_values"]["right"], 36)
            self.assertEqual(audit["computed_values"]["left"], 74)
            self.assertEqual(audit["difference"], 38)
            self.assertFalse(any("Please confirm" in n.value for n in app.warning))
            self.assertFalse(any("Needs confirmation" in n.value for n in app.markdown))
            self.assertIn("**Confirmed mapping**", [n.value for n in app.markdown])
            self.assertIn("after", [n.value for n in app.markdown])
            self.assertIn("before", [n.value for n in app.markdown])
            # Rendering must not rewrite the original mapper proposal.
            self.assertTrue(app.session_state["schema_mapping_result"]["needs_confirmation"])
            next(s for s in app.selectbox if s.label == "Segment column for breakdown").select("segment")
            app.checkbox(key="_investigation_confirmed_widget").check()
            next(b for b in app.button if b.label == "Investigate hidden pattern").click().run()
            next(b for b in app.button if b.label == "Run stress tests").click().run()
            next(b for b in app.button if b.label == "Generate final verdict").click().run()
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(any("Please confirm" in n.value for n in app.warning))
            self.assertEqual(app.session_state["audit_mapping"], expected)
            self.assertEqual(app.session_state["extracted_claim"], CLAIM)
            for key in ("dataset_bytes", "investigation_result", "critic_result", "verdict_result"):
                self.assertIn(key, app.session_state)

    def test_target_fields_are_part_of_the_persisted_submission(self):
        from ui.audit_form_state import initialize_widgets, widget_keys, capture_submission
        state = {}
        keys = widget_keys(0)
        initialize_widgets(state, keys, {}, "score")
        for field, value in dict(metric="score", calculation_type="overall", aggregation="sum", operator="equal",
                                 has_target=True, target=123.0, target_kind="absolute", confirmed=True).items():
            state[keys[field]] = value
        capture_submission(state, keys)
        request = state["audit_submission"]["request"]
        self.assertEqual(request["target"], 123)
        self.assertEqual(request["operator"], "equal")
        self.assertIsNone(request["left"])
        self.assertIsNone(request["group_column"])


if __name__ == "__main__":
    unittest.main()
