"""Sequential controls and existing deterministic evidence presentation."""

import io
from copy import deepcopy
import unittest
from unittest.mock import patch

import pandas as pd

from core.auditor import audit_claim
from test_ui_presentation import seeded_app, PAYLOAD, CLAIM, MAPPING, walk
from ui.audit_summary import audit_summary


def audited_app(demo=False):
    app = seeded_app()
    app.session_state["audit_mapping"] = MAPPING
    app.session_state["audit_result"] = audit_claim(pd.read_csv(io.BytesIO(PAYLOAD)), CLAIM, MAPPING)
    app.session_state["demo_mode"] = demo
    return app


class AnalysisFlowTests(unittest.TestCase):
    def test_summary_is_readable_and_raw_evidence_is_collapsed(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = audited_app().run(timeout=30)
        self.assertFalse(app.exception)
        text = " ".join(n.value for n in app.markdown)
        self.assertIn("The average score increased from 36 to 74, a change of +38.", text)
        self.assertNotIn("Supported: {'left'", text)
        for node, ancestors in walk(app.main):
            if node.type == "json":
                self.assertTrue(any(p.type == "expander" and not p.proto.expanded for p in ancestors))

    def test_full_sequence_demo_preselection_and_no_automatic_stages(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)), \
             patch("app.investigate_segments", wraps=__import__('core.investigator', fromlist=['investigate_segments']).investigate_segments) as investigate, \
             patch("app.run_critic", wraps=__import__('core.critic', fromlist=['run_critic']).run_critic) as critic, \
             patch("app.generate_verdict") as verdict:
            app = audited_app(demo=True).run(timeout=30)
            labels = [b.label for b in app.button]
            self.assertIn("Investigate hidden pattern", labels)
            self.assertNotIn("Run stress tests", labels)
            self.assertNotIn("Generate final verdict", labels)
            self.assertEqual(next(s for s in app.selectbox if s.label == "Segment column for breakdown").value, "segment")
            investigate.assert_not_called(); critic.assert_not_called(); verdict.assert_not_called()
            next(c for c in app.checkbox if c.label.startswith("I confirm this segment")).check()
            next(b for b in app.button if b.label == "Investigate hidden pattern").click().run()
            self.assertFalse(app.exception)
            investigate.assert_called_once(); critic.assert_not_called()
            self.assertEqual(next(s for s in app.selectbox if s.label.startswith("Segment column for leave")).value, "segment")
            self.assertNotIn("Generate final verdict", [b.label for b in app.button])
            next(b for b in app.button if b.label == "Run stress tests").click().run()
            self.assertFalse(app.exception)
            critic.assert_called_once(); verdict.assert_not_called()
            self.assertIn("Generate final verdict", [b.label for b in app.button])
            headings = [n.value for n in app.subheader]
            self.assertLess(headings.index("Self-Doubt / Stress Test"), headings.index("Final Verdict"))

    def test_completed_critic_reveals_verdict_regardless_of_check_outcomes(self):
        from core.critic import run_critic
        from core.investigator import investigate_segments
        from core.verdict import generate_verdict

        data = pd.read_csv(io.BytesIO(PAYLOAD))
        audit = audit_claim(data, CLAIM, MAPPING)
        investigation = investigate_segments(data, CLAIM, audit, MAPPING, "segment", True)
        original = run_critic(data, CLAIM, audit, MAPPING)
        for statuses in (("held",) * 5, ("failed",) * 5, ("inconclusive",) * 5,
                         ("held", "failed", "inconclusive", "inconclusive", "not_applicable")):
            with self.subTest(statuses=statuses), patch("app.map_schema", return_value={}), \
                 patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)), \
             patch("app.generate_verdict", side_effect=lambda *a, **kw: generate_verdict(*a, use_model=False)):
                critic = deepcopy(original)
                for check, status in zip(critic["checks_run"], statuses):
                    check["status"] = status
                critic["checks_passed"] = statuses.count("held")
                critic["checks_failed"] = statuses.count("failed")
                critic["checks_inconclusive"] = statuses.count("inconclusive")
                critic["failed_checks"] = [c["name"] for c in critic["checks_run"] if c["status"] == "failed"]
                app = audited_app(demo=True)
                app.session_state["investigation_result"] = investigation
                app.session_state["critic_result"] = critic
                app.run(timeout=30)
                self.assertFalse(app.exception)
                headings = [n.value for n in app.subheader]
                self.assertLess(headings.index("Self-Doubt / Stress Test"), headings.index("Final Verdict"))
                upstream = {k: deepcopy(app.session_state[k]) for k in (
                    "dataset_id", "claim_input", "extracted_claim", "audit_mapping", "audit_result",
                    "investigation_result", "critic_result")}
                next(b for b in app.button if b.label == "Generate final verdict").click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.session_state["verdict_result"])
                for key, value in upstream.items():
                    self.assertEqual(app.session_state[key], value, key)

    def test_verdict_heading_hidden_before_critic_completion(self):
        with patch("app.map_schema", return_value={}), \
             patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = audited_app().run(timeout=30)
            next(b for b in app.button if b.label == "Skip investigation").click().run()
            self.assertNotIn("Final Verdict", [n.value for n in app.subheader])
            self.assertNotIn("Generate final verdict", [b.label for b in app.button])

    def test_arbitrary_dataset_no_segment_guess_and_explicit_skip(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)), patch("app.run_critic") as critic:
            app = audited_app(demo=False).run(timeout=30)
            self.assertIsNone(next(s for s in app.selectbox if s.label == "Segment column for breakdown").value)
            next(b for b in app.button if b.label == "Skip investigation").click().run()
            self.assertFalse(app.exception)
            self.assertIn("Run stress tests", [b.label for b in app.button])
            self.assertNotIn("Generate final verdict", [b.label for b in app.button])
            self.assertTrue(any("explicitly skipped" in n.value for n in app.info))
            critic.assert_not_called()

    def test_overall_summary_uses_existing_value(self):
        self.assertEqual(audit_summary({"metric":"revenue", "computed_values":{"overall":123}}, {"aggregation":"sum"}),
                         "The total revenue across the dataset was 123.")


if __name__ == "__main__":
    unittest.main()
