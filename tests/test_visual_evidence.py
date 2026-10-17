"""Chart values, receipt provenance, graceful absence, and UI credential isolation."""

import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim
from core.investigator import investigate_segments
from core.critic import run_critic
from core.verdict import generate_verdict
from tools.visuals import evidence_charts
from tools.receipts import computational_receipt


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "synthetic_simpson.csv"
CLAIM = {"claim_type": "comparison", "metric": "score", "original_claim": "The overall metric improved."}
MAPPING = dict(confirmed=True, calculation_type="two_periods", metric="score", aggregation="mean",
               operator="greater", group_column="period", left="after", right="before")


def evidence(data=None):
    data = pd.read_csv(FIXTURE) if data is None else data
    audit = audit_claim(data, CLAIM, MAPPING)
    inv = investigate_segments(data, CLAIM, audit, MAPPING, "segment", True) if "segment" in data else None
    critic = run_critic(data, CLAIM, audit, MAPPING)
    return audit, inv, critic


class VisualEvidenceTests(unittest.TestCase):
    def test_simpson_chart_values(self):
        audit, inv, critic = evidence()
        charts = evidence_charts(audit, inv, critic)
        self.assertEqual([r["value"] for r in charts["aggregate"]["data"]["values"]], [36, 74])
        rows = charts["segments"]["data"]["values"]
        self.assertEqual([r["value"] for r in rows], [90, 80, 30, 20])
        weights = charts["composition"]["data"]["values"]
        self.assertEqual([r["value"] for r in weights], [0.1, 0.9, 0.9, 0.1])
        self.assertEqual(charts["composition"]["encoding"]["y"]["scale"]["domain"], [0, 1])
        self.assertEqual(audit["status"], "Supported")

    def test_stress_charts_match_calculations(self):
        data = pd.DataFrame({"period": ["before"] * 20 + ["after"] * 20,
                             "score": [5] * 20 + [1] * 19 + [1000]})
        audit, inv, critic = evidence(data)
        charts = evidence_charts(audit, inv, critic)
        for name in ("mean_vs_median", "outlier_removal"):
            check = next(c for c in critic["checks_run"] if c["name"] == name)
            self.assertEqual(check["status"], "failed")
            expected = [check[key]["computed_values"][side] for side in ("right", "left")
                        for key in ("original_result", "stress_result")]
            self.assertEqual([r["value"] for r in charts[name]["data"]["values"]], expected)

    def test_receipt_mappings_counts_and_rules(self):
        audit, inv, critic = evidence()
        receipt = computational_receipt("segment_investigation", inv, MAPPING)
        self.assertEqual(receipt["columns_used"], ["score", "period", "segment"])
        self.assertEqual(receipt["filters_or_buckets"]["left"], "after")
        self.assertEqual(receipt["rows_analyzed"], {"left": 20, "right": 20})
        self.assertIn("delta_mean", receipt["formula_or_rule"])
        self.assertEqual(receipt["result"], "direction_reversal")
        self.assertEqual(receipt["dataset_fingerprint"], inv["computational_receipt"]["data_sha256"])
        self.assertTrue(receipt["limitations"])
        audit_receipt = computational_receipt("audit", audit, MAPPING, dataset_fingerprint="csv-sha256")
        self.assertEqual(audit_receipt["computed_values"]["left"], 74)
        self.assertEqual(audit_receipt["confirmed_mapping"], MAPPING)
        self.assertEqual(audit_receipt["comparison"]["operator"], "greater")
        self.assertEqual(audit_receipt["difference"], 38)
        self.assertEqual(audit_receipt["rows_analyzed"]["right"]["rows"], 20)
        self.assertIn("left - right", audit_receipt["formula_or_rule"])
        check = next(c for c in critic["checks_run"] if c["name"] == "bootstrap")
        bootstrap = computational_receipt("bootstrap", check, MAPPING, critic)
        self.assertEqual(bootstrap["upstream_receipt"]["seed"], 20261016)
        self.assertEqual(bootstrap["dataset_fingerprint"], critic["computational_receipts"]["data_sha256"])

    def test_verdict_proof_preserves_inputs(self):
        audit, inv, critic = evidence()
        verdict = generate_verdict(CLAIM, audit, inv, critic, use_model=False)
        receipt = computational_receipt("verdict", verdict)
        self.assertEqual(receipt["result"], "Partially supported")
        self.assertEqual(receipt["formula_or_rule"]["decision_rule"], "R6")
        self.assertEqual(receipt["upstream_receipt"]["inputs"]["audit"], audit)

    def test_missing_and_non_applicable_data(self):
        self.assertTrue(all(chart is None for chart in evidence_charts().values()))
        self.assertIsNone(evidence_charts({"computed_values": {"left": float("nan"), "right": 1}})["aggregate"])
        critic = {"checks_run": [{"name": "mean_vs_median", "status": "not_applicable"}]}
        self.assertIsNone(evidence_charts(critic=critic)["mean_vs_median"])
        self.assertIsNone(evidence_charts(investigation={"finding": "inconclusive"})["segments"])
        receipt = computational_receipt("missing", None)
        self.assertEqual(receipt["rows_analyzed"], "Not recorded in upstream output")

    def test_ui_renders_charts_proofs_and_no_credentials(self):
        payload = FIXTURE.read_bytes()
        audit, inv, critic = evidence()
        verdict = generate_verdict(CLAIM, audit, inv, critic, use_model=False)
        sentinel = "FAKE_TEST_ONLY_NEVER_DISPLAY_12345"
        with patch.dict(os.environ, {"NEBIUS_API_KEY": sentinel}), patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(payload)):
            app = AppTest.from_string("from app import main\nmain()")
            for key, value in {"dataset_id": hashlib.sha256(payload).hexdigest(), "extracted_claim": CLAIM,
                               "audit_mapping": MAPPING, "audit_result": audit, "investigation_result": inv,
                               "critic_result": critic, "verdict_result": verdict}.items():
                app.session_state[key] = value
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertGreater(len(app.get("vega_lite_chart")) + len(app.get("arrow_vega_lite_chart")), 0)
            self.assertTrue(any("Show proof" in e.label for e in app.expander))
            rendered = " ".join([item.value for item in app.markdown] + [item.value for item in app.json])
            self.assertNotIn(sentinel, rendered)
            self.assertNotIn("NEBIUS_API_KEY", rendered)
            self.assertIn("Partially supported", rendered)
            self.assertTrue(any("inconclusive" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
