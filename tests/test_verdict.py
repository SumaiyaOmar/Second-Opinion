"""Final statuses, Simpson qualification, safe language and model fallback."""

import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim
from core.critic import run_critic
from core.investigator import investigate_segments
from core.verdict import generate_verdict
from test_critic import CLAIM, MAPPING, robust_data


def evidence(data=None, mapping=None):
    data = robust_data() if data is None else data
    mapping = MAPPING if mapping is None else mapping
    audit = audit_claim(data, CLAIM, mapping)
    critic = run_critic(data, CLAIM, audit, mapping, "segment" if "segment" in data else None, "segment" in data)
    return audit, critic


class VerdictTests(unittest.TestCase):
    def test_supported_without_investigator(self):
        audit, critic = evidence()
        result = generate_verdict(CLAIM, audit, critic=critic, use_model=False)
        self.assertEqual(result["final_status"], "Supported")
        self.assertTrue(any("No segment investigation" in item for item in result["limitations"]))

    def test_simpson_is_partial_not_unsupported(self):
        data = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "synthetic_simpson.csv")
        claim = {**CLAIM, "original_claim": "The overall metric improved."}
        mapping = {**MAPPING, "left": "after", "right": "before"}
        audit = audit_claim(data, claim, mapping)
        inv = investigate_segments(data, claim, audit, mapping, "segment", True)
        critic = run_critic(data, claim, audit, mapping, "segment", True, inv)
        result = generate_verdict(claim, audit, inv, critic, use_model=False)
        self.assertEqual(audit["status"], "Supported")
        self.assertEqual(result["final_status"], "Partially supported")
        for text in ("36", "74", "Every underlying segment declined", "segment composition"):
            self.assertIn(text, result["corrected_conclusion"])

    def test_numerically_contradicted(self):
        audit, critic = evidence(mapping={**MAPPING, "operator": "less"})
        self.assertEqual(generate_verdict(CLAIM, audit, critic=critic, use_model=False)["final_status"], "Unsupported")
        self.assertEqual(generate_verdict(CLAIM, audit, use_model=False)["final_status"], "Unsupported")

    def test_missing_or_unresolved_evidence(self):
        audit, critic = evidence()
        for bad_audit, bad_critic in (({}, critic), (audit, None), ({**audit, "status": "Inconclusive"}, critic)):
            self.assertEqual(generate_verdict(CLAIM, bad_audit, critic=bad_critic, use_model=False)["final_status"], "Inconclusive")
        unresolved = copy.deepcopy(critic)
        for check in unresolved["checks_run"]:
            check["status"] = "inconclusive"
        unresolved.update(checks_passed=0, checks_failed=0, checks_inconclusive=5)
        self.assertEqual(generate_verdict(CLAIM, audit, critic=unresolved, use_model=False)["final_status"], "Inconclusive")

    def test_supported_but_fragile_is_partial(self):
        data = pd.DataFrame({"period": ["2026-02"] * 20 + ["2026-03"] * 20,
                             "score": [5] * 20 + [1] * 19 + [1000]})
        audit, critic = evidence(data)
        result = generate_verdict(CLAIM, audit, critic=critic, use_model=False)
        self.assertEqual(audit["status"], "Supported")
        self.assertEqual(result["final_status"], "Partially supported")
        self.assertIn("outlier_removal", result["corrected_conclusion"])

    @patch("core.verdict.get_nebius_client", side_effect=RuntimeError("private error detail"))
    def test_model_failure_returns_deterministic_fallback(self, factory):
        audit, critic = evidence()
        result = generate_verdict(CLAIM, audit, critic=critic)
        self.assertEqual(result["final_status"], "Supported")
        self.assertTrue(result["corrected_conclusion"])
        self.assertEqual(result["computational_receipts"]["explanation_source"], "deterministic_fallback")
        self.assertNotIn("private error detail", json.dumps(result))

    @patch("core.verdict.get_nebius_client")
    def test_unapproved_model_output_rejected(self, factory):
        factory.return_value.__enter__.return_value.chat.completions.create.return_value.choices[0].message.content = json.dumps({"corrected_conclusion": "Revenue is 9999 and proves the true cause."})
        audit, critic = evidence()
        result = generate_verdict(CLAIM, audit, critic=critic)
        self.assertNotIn("9999", result["corrected_conclusion"])
        self.assertEqual(result["computational_receipts"]["explanation_source"], "deterministic_fallback")

    @patch("core.verdict.get_nebius_client")
    def test_valid_model_output_keeps_frozen_status_and_inputs(self, factory):
        audit, critic = evidence()
        before = copy.deepcopy((audit, critic))
        create = factory.return_value.__enter__.return_value.chat.completions.create
        def reply(**kwargs):
            approved = json.loads(kwargs["messages"][1]["content"])["approved_conclusions"]
            response = unittest.mock.MagicMock()
            response.choices[0].message.content = json.dumps({"corrected_conclusion": approved[-1]})
            return response
        create.side_effect = reply
        result = generate_verdict(CLAIM, audit, critic=critic)
        self.assertEqual(result["final_status"], "Supported")
        self.assertEqual(result["computational_receipts"]["explanation_source"], "nebius_validated")
        self.assertEqual((audit, critic), before)

    def test_inconclusive_investigation(self):
        audit, critic = evidence()
        result = generate_verdict(CLAIM, audit, {"finding": "inconclusive"}, critic, use_model=False)
        self.assertEqual(result["final_status"], "Inconclusive")

    @patch("core.verdict.get_nebius_client", side_effect=RuntimeError("offline"))
    def test_ui_fallback_and_upstream_invalidation(self, factory):
        payload = robust_data().to_csv(index=False).encode()
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(payload)), patch("app.extract_claim", return_value=CLAIM):
            app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
            app.text_area[0].set_value(CLAIM["original_claim"])
            next(b for b in app.button if b.label == "Analyze claim").click().run()
            app.selectbox[1].select("two_periods")
            app.selectbox[2].select("mean")
            app.selectbox[3].select("greater")
            app.selectbox[4].select("period")
            app.text_input[0].set_value("2026-03")
            app.text_input[1].set_value("2026-02")
            app.checkbox[1].check()
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            next(b for b in app.button if b.label == "Skip investigation").click().run()
            next(b for b in app.button if b.label == "Run stress tests").click().run()
            next(b for b in app.button if b.label == "Generate final verdict").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["verdict_result"]["final_status"], "Supported")
            self.assertTrue(any("Verified version" in m.value for m in app.markdown))
            next(b for b in app.button if b.label == "Run stress tests").click().run()
            with self.assertRaises(KeyError):
                app.session_state["verdict_result"]


if __name__ == "__main__":
    unittest.main()
