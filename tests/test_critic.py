"""Frozen Critic rules tested on robust, sensitive, and ineligible examples."""

import io
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.auditor import audit_claim
from core.critic import run_critic
from core.investigator import investigate_segments


CLAIM = {"claim_type": "comparison", "metric": "score", "original_claim": "Mean score increased."}
MAPPING = dict(confirmed=True, calculation_type="two_periods", metric="score",
               aggregation="mean", operator="greater", group_column="period",
               left="2026-03", right="2026-02")


def robust_data():
    return pd.DataFrame([
        {"period": period, "segment": segment, "score": value}
        for period, value in (("2026-01", 0), ("2026-02", 10), ("2026-03", 20), ("2026-04", 30))
        for segment in ("A", "B") for _ in range(20)
    ])


def run(data, mapping=None, **options):
    mapping = MAPPING if mapping is None else mapping
    return run_critic(data, CLAIM, audit_claim(data, CLAIM, mapping), mapping,
                      **{"segment_column": "segment", "segment_confirmed": True, **options})


def check(result, name):
    return next(item for item in result["checks_run"] if item["name"] == name)


class CriticTests(unittest.TestCase):
    def test_robust_conclusion_holds_all_five(self):
        result = run(robust_data())
        self.assertEqual(result["checks_passed"], 5)
        self.assertEqual(result["checks_failed"], 0)
        self.assertEqual(result["checks_inconclusive"], 0)
        self.assertIn("Held 5 of 5 applicable checks", result["stability_summary"])
        self.assertEqual(check(result, "alternative_window")["receipt"]["left_bins"], ["2026-03", "2026-04"])

    def test_one_segment_drives_conclusion(self):
        data = robust_data()
        for period, segment, value in (("2026-02", "A", 0), ("2026-02", "B", 20),
                                       ("2026-03", "A", 30), ("2026-03", "B", 10)):
            data.loc[(data.period == period) & (data.segment == segment), "score"] = value
        result = run(data)
        trial = check(result, "leave_one_segment_out")
        self.assertEqual(trial["status"], "failed")
        removed_a = next(row for row in trial["stress_result"] if row["removed_segment"] == "A")
        self.assertEqual(removed_a["result"]["difference"], -10)
        self.assertIn(trial, result["failed_checks"])

    def test_outlier_mean_reverses_under_filter_and_median(self):
        data = pd.DataFrame({"period": ["2026-02"] * 20 + ["2026-03"] * 20,
                             "score": [5] * 20 + [1] * 19 + [1000]})
        result = run(data, segment_column=None, segment_confirmed=False)
        for name in ("outlier_removal", "mean_vs_median"):
            self.assertEqual(check(result, name)["status"], "failed")
            self.assertEqual(check(result, name)["stress_result"]["difference"], -4)
        self.assertEqual(check(result, "outlier_removal")["receipt"]["removed_selected_rows"], 1)

    def test_insufficient_bootstrap(self):
        data = robust_data().groupby(["period", "segment"]).head(1)
        self.assertEqual(check(run(data), "bootstrap")["status"], "inconclusive")

    def test_not_applicable_checks(self):
        result = run(robust_data(), {**MAPPING, "calculation_type": "two_groups", "aggregation": "sum"},
                     segment_column=None, segment_confirmed=False)
        for name in ("alternative_window", "mean_vs_median", "leave_one_segment_out"):
            self.assertEqual(check(result, name)["status"], "not_applicable")
        self.assertEqual(result["checks_passed"] + result["checks_failed"] + result["checks_inconclusive"], 2)

    def test_reproducible_bootstrap(self):
        data = robust_data()
        data["score"] = data.score + [i % 7 for i in range(len(data))]
        self.assertEqual(check(run(data), "bootstrap"), check(run(data), "bootstrap"))

    def test_missing_windows_are_inconclusive(self):
        data = robust_data()
        data = data[data.period != "2026-01"]
        self.assertEqual(check(run(data), "alternative_window")["status"], "inconclusive")

    def test_median_material_change_without_direction_reversal(self):
        data = pd.DataFrame({"period": ["2026-02"] * 20 + ["2026-03"] * 20,
                             "score": [1] * 20 + [2] * 19 + [200]})
        result = check(run(data, segment_column=None, segment_confirmed=False), "mean_vs_median")
        self.assertEqual(result["stress_result"]["direction"], 1)
        self.assertEqual(result["status"], "failed")

    def test_bootstrap_interval_spanning_zero_is_inconclusive(self):
        data = pd.DataFrame({"period": ["2026-02"] * 20 + ["2026-03"] * 20,
                             "score": [0, 100] * 10 + [1, 101] * 10})
        result = check(run(data, segment_column=None, segment_confirmed=False), "bootstrap")
        self.assertEqual(result["status"], "inconclusive")
        low, high = result["stress_result"]["difference_interval"]
        self.assertLess(low, 0)
        self.assertGreater(high, 0)

    def test_overall_mean_against_target(self):
        mapping = {**MAPPING, "calculation_type": "overall", "group_column": None,
                   "left": None, "right": None, "target": -10}
        result = run(robust_data(), mapping)
        self.assertEqual(check(result, "alternative_window")["status"], "not_applicable")
        self.assertEqual(check(result, "bootstrap")["status"], "held")

    def test_expanded_window_can_fail(self):
        data = robust_data()
        data.loc[data.period == "2026-04", "score"] = -100
        self.assertEqual(check(run(data), "alternative_window")["status"], "failed")

    def test_missing_values_and_stale_audit(self):
        data = robust_data()
        audit = audit_claim(data, CLAIM, MAPPING)
        data.loc[data.period == "2026-03", "score"] = 50
        result = run_critic(data, CLAIM, audit, MAPPING)
        self.assertEqual(result["checks_inconclusive"], 5)
        data.loc[40, "score"] = float("nan")
        self.assertEqual(run(data)["checks_inconclusive"], 5)

    def test_investigation_not_silently_confirmed_by_median_bootstrap(self):
        data = robust_data()
        audit = audit_claim(data, CLAIM, MAPPING)
        inv = investigate_segments(data, CLAIM, audit, MAPPING, "segment", True)
        result = run(data, investigation_result=inv)
        self.assertEqual(check(result, "mean_vs_median")["status"], "inconclusive")
        self.assertEqual(check(result, "bootstrap")["status"], "inconclusive")
        self.assertEqual(check(result, "leave_one_segment_out")["status"], "inconclusive")

    def test_ui_failed_checks_visible_and_reset_on_audit(self):
        data = pd.DataFrame({"period": ["2026-02"] * 20 + ["2026-03"] * 20,
                             "score": [5] * 20 + [1] * 19 + [1000]})
        payload = data.to_csv(index=False).encode()
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(payload)), patch("app.extract_claim", return_value=CLAIM):
            app = AppTest.from_string("from app import main\nmain()").run()
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
            next(button for button in app.button if button.label == "Run stress tests").click().run()
            self.assertFalse(app.exception)
            self.assertGreaterEqual(app.session_state["critic_result"]["checks_failed"], 2)
            self.assertTrue(any("Outlier-removal check" in warning.value for warning in app.warning))
            self.assertGreater(len(app.expander), 0)
            app.selectbox[3].select("less")
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            with self.assertRaises(KeyError):
                app.session_state["critic_result"]


if __name__ == "__main__":
    unittest.main()
