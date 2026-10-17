"""Deterministic audit cases and mapping safeguards."""

import unittest
import io
import json
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim


CLAIM = {"claim_type": "comparison", "metric": "revenue", "original_claim": "Revenue increased."}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "period": ["Q1", "Q1", "Q2", "Q2"],
            "segment": ["A", "B", "A", "B"], "revenue": [40, 60, 70, 80],
        })
        self.config = dict(confirmed=True, calculation_type="two_periods", metric="revenue",
                           aggregation="sum", operator="greater", group_column="period",
                           left="Q2", right="Q1")

    def audit(self, **updates):
        return audit_claim(self.data, CLAIM, {**self.config, **updates})

    def test_supported_period_comparison(self):
        result = self.audit()
        self.assertEqual(result["status"], "Supported")
        self.assertEqual(result["computed_values"]["left"], 150)
        self.assertEqual(result["computed_values"]["right"], 100)
        self.assertEqual(result["difference"], 50)

    def test_unsupported_claim(self):
        self.assertEqual(self.audit(operator="less")["status"], "Unsupported")

    def test_missing_and_ambiguous_mapping(self):
        self.assertEqual(self.audit(metric="profit")["status"], "Inconclusive")
        self.assertEqual(audit_claim(self.data, CLAIM)["status"], "Inconclusive")
        self.data.columns = ["period", "revenue", "revenue"]
        self.assertEqual(self.audit()["status"], "Inconclusive")

    def test_overall_metric(self):
        result = self.audit(calculation_type="overall", group_column=None, left=None,
                            right=None, target=250, operator="equal")
        self.assertEqual(result["status"], "Supported")
        self.assertEqual(result["computed_values"]["overall"], 250)

    def test_segment_mean(self):
        result = self.audit(calculation_type="two_groups", group_column="segment",
                            left="B", right="A", aggregation="mean")
        self.assertEqual(result["status"], "Supported")
        self.assertEqual(result["difference"], 15)

    def test_percent_and_partial_amount(self):
        self.assertEqual(self.audit(target=50, target_kind="percent")["status"], "Supported")
        self.assertEqual(self.audit(target=75, target_kind="percent")["status"], "Partially supported")

    def test_zero_baseline(self):
        self.data.loc[self.data.period == "Q1", "revenue"] = 0
        self.assertEqual(self.audit(target=10, target_kind="percent")["status"], "Inconclusive")

    def test_missing_values_do_not_get_full_support(self):
        self.data.loc[2, "revenue"] = float("nan")
        self.assertEqual(self.audit(operator="less")["status"], "Partially supported")
        self.assertEqual(self.audit()["status"], "Inconclusive")

    def test_empty_bucket_and_nonfinite_values(self):
        self.assertEqual(self.audit(left="Q3")["status"], "Inconclusive")
        self.data["revenue"] = self.data.revenue.astype(float)
        self.data.loc[0, "revenue"] = float("inf")
        self.assertEqual(self.audit()["status"], "Inconclusive")

    def test_no_implicit_numeric_coercion(self):
        self.data["revenue"] = self.data.revenue.astype(str)
        self.assertEqual(self.audit()["status"], "Inconclusive")

    def test_large_integer_total_does_not_wrap(self):
        self.data["revenue"] = [2**62] * 4
        result = self.audit(calculation_type="overall", group_column=None, left=None,
                            right=None, target=2**64, operator="equal")
        self.assertEqual(result["status"], "Supported")
        self.assertEqual(result["computed_values"]["overall"], 2**64)

    def test_unsupported_claim_type(self):
        result = audit_claim(self.data, {**CLAIM, "claim_type": "causal"}, self.config)
        self.assertEqual(result["status"], "Inconclusive")

    def test_app_confirmed_audit_and_persistence(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(b"period,revenue\nQ1,100\nQ2,150\n")), patch("app.extract_claim", return_value=CLAIM) as extract:
            app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
            app.text_area[0].set_value(CLAIM["original_claim"])
            next(b for b in app.button if b.label == "Analyze claim").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(next(json.loads(x.value)["status"] for x in app.json if "calculation_type" in json.loads(x.value)), "Inconclusive")
            app.selectbox[1].select("two_periods")
            app.selectbox[2].select("sum")
            app.selectbox[3].select("greater")
            app.selectbox[4].select("period")
            app.text_input[0].set_value("Q2")
            app.text_input[1].set_value("Q1")
            app.checkbox[1].check()
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            self.assertFalse(app.exception)
            result = app.session_state["audit_result"]
            self.assertEqual(result["status"], "Supported")
            self.assertEqual(result["difference"], 50)
            self.assertIn("left - right", app.code[0].value)
            app.run()
            self.assertEqual(next(json.loads(x.value)["status"] for x in app.json if "calculation_type" in json.loads(x.value)), "Supported")
            extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()
