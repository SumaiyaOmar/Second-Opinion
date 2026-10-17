"""Synthetic segment evidence, reconciliation, gating, and UI regression tests."""

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim
from core.investigator import investigate_segments


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "synthetic_simpson.csv"
CLAIM = {"claim_type": "comparison", "metric": "score", "original_claim": "Mean score increased after versus before."}
MAPPING = dict(confirmed=True, calculation_type="two_periods", metric="score",
               aggregation="mean", operator="greater", group_column="period",
               left="after", right="before")


class InvestigatorTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.read_csv(FIXTURE)

    def investigate(self, data=None, mapping=None, **options):
        data = self.data if data is None else data
        mapping = MAPPING if mapping is None else mapping
        audit = audit_claim(data, CLAIM, mapping)
        return investigate_segments(data, CLAIM, audit, mapping,
                                    **{"segment_column": "segment", "segment_confirmed": True, **options})

    def test_simpson_reversal(self):
        result = self.investigate()
        self.assertEqual(result["finding"], "direction_reversal")
        self.assertEqual(result["overall_change"]["right"], 36)
        self.assertEqual(result["overall_change"]["left"], 74)
        self.assertTrue(all(row["change"] == -10 for row in result["segment_results"]))
        effects = result["mix_shift_evidence"]
        self.assertAlmostEqual(effects["within_effect"], -10)
        self.assertAlmostEqual(effects["mix_effect"], 48)
        self.assertAlmostEqual(effects["residual"], 0)
        self.assertEqual(result["strongest_supported_driver"]["component"], "mix_effect")
        for side in ("left", "right"):
            self.assertAlmostEqual(sum(row[f"{side}_share"] for row in result["segment_weights"]), 1)

    def test_segments_and_aggregate_improve(self):
        data = pd.DataFrame({"period": ["before"] * 4 + ["after"] * 4,
                             "segment": ["high", "high", "low", "low"] * 2,
                             "score": [90, 90, 30, 30, 100, 100, 40, 40]})
        result = self.investigate(data)
        self.assertEqual(result["finding"], "no_material_mix_effect")
        self.assertEqual(result["overall_change"]["change"], 10)
        self.assertTrue(all(row["change"] > 0 for row in result["segment_results"]))

    def test_mix_without_full_reversal(self):
        self.data.loc[(self.data.period == "after") & (self.data.segment == "low"), "score"] = 40
        result = self.investigate()
        self.assertEqual(result["finding"], "mix_shift")
        self.assertTrue(any(row["change"] > 0 for row in result["segment_results"]))

    def test_insufficient_segments(self):
        self.assertEqual(self.investigate(self.data[self.data.segment == "high"])["finding"], "inconclusive")

    def test_missing_mappings_and_confirmation(self):
        for options in ({"segment_column": None}, {"segment_confirmed": False}, {"segment_column": "missing"}):
            result = self.investigate(**options)
            self.assertEqual(result["finding"], "inconclusive")
            self.assertFalse(result["computational_receipt"]["executed"])
        self.assertEqual(self.investigate(mapping={})["finding"], "inconclusive")

    def test_small_or_unmatched_segments(self):
        data = self.data.drop(index=0)
        self.assertEqual(self.investigate(data)["finding"], "inconclusive")
        data = self.data.copy()
        data.loc[0:1, "segment"] = "new"
        self.assertEqual(self.investigate(data)["finding"], "inconclusive")

    def test_missing_or_nonfinite_values(self):
        data = self.data.copy()
        data.loc[0, "segment"] = None
        self.assertEqual(self.investigate(data)["finding"], "inconclusive")
        data = self.data.copy()
        data["score"] = data.score.astype(float)
        for value in (float("nan"), float("inf")):
            data.loc[0, "score"] = value
            self.assertEqual(self.investigate(data)["finding"], "inconclusive")

    def test_stale_audit_rejected(self):
        audit = audit_claim(self.data, CLAIM, MAPPING)
        self.data.loc[0, "score"] = 95
        result = investigate_segments(self.data, CLAIM, audit, MAPPING, "segment", True)
        self.assertEqual(result["finding"], "inconclusive")

    def test_sum_decomposition_with_volume(self):
        data = pd.concat([self.data, self.data[self.data.period == "after"]], ignore_index=True)
        result = self.investigate(data, {**MAPPING, "aggregation": "sum"})
        self.assertNotEqual(result["finding"], "direction_reversal")
        effects = result["mix_shift_evidence"]
        self.assertAlmostEqual(effects["reconstructed_change"], result["overall_change"]["change"])
        self.assertNotEqual(effects["volume_effect"], 0)

    def test_two_group_comparison(self):
        self.assertEqual(self.investigate(mapping={**MAPPING, "calculation_type": "two_groups"})["finding"], "direction_reversal")

    def test_swapping_buckets_reverses_decomposition(self):
        forward = self.investigate()
        backward = self.investigate(mapping={**MAPPING, "left": "before", "right": "after"})
        self.assertEqual(backward["finding"], "direction_reversal")
        for component in ("within_effect", "mix_effect", "reconstructed_change"):
            self.assertAlmostEqual(forward["mix_shift_evidence"][component], -backward["mix_shift_evidence"][component])

    def test_overall_audit_is_not_eligible(self):
        mapping = {**MAPPING, "calculation_type": "overall", "group_column": None,
                   "left": None, "right": None, "target": 0}
        self.assertEqual(self.investigate(mapping=mapping)["finding"], "inconclusive")

    def test_tiny_numerical_changes_do_not_reverse(self):
        self.data["score"] = 1.0
        self.data.loc[self.data.period == "after", "score"] = 1.0 + 1e-12
        self.assertEqual(self.investigate()["finding"], "no_material_mix_effect")

    def test_ui_investigation(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(FIXTURE.read_bytes())), patch("app.extract_claim", return_value=CLAIM):
            app = AppTest.from_string("from app import main\nmain()").run()
            app.text_area[0].set_value(CLAIM["original_claim"])
            next(b for b in app.button if b.label == "Analyze claim").click().run()
            app.selectbox[1].select("two_periods")
            app.selectbox[2].select("mean")
            app.selectbox[3].select("greater")
            app.selectbox[4].select("period")
            app.text_input[0].set_value("after")
            app.text_input[1].set_value("before")
            app.checkbox[1].check()
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            app.selectbox[6].select("segment")
            app.checkbox[2].check()
            next(b for b in app.button if b.label == "Investigate hidden pattern").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["investigation_result"]["finding"], "direction_reversal")
            self.assertTrue(app.session_state["investigation_result"]["computational_receipt"]["executed"])
            app.selectbox[3].select("less")
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            with self.assertRaises(KeyError):
                app.session_state["investigation_result"]


if __name__ == "__main__":
    unittest.main()
