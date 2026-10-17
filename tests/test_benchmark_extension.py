"""Count provenance, semantic isolation and mapping-required scoring."""

from pathlib import Path
import tempfile
import unittest

from benchmark.cases import load_documented_cases
from benchmark.semantic import semantic_cases, rules_interpret, predict_semantic, interpretation_metrics
from benchmark.metrics import score_row, summarize
from benchmark.run import run_benchmark
from core.auditor import audit_claim
from core.investigator import investigate_segments


class BenchmarkExtensionTests(unittest.TestCase):
    def test_kidney_counts_and_provenance(self):
        case = load_documented_cases(Path(__file__).resolve().parents[1] / "benchmark/documented/manifest.json")[0]
        self.assertEqual(len(case.inputs.data), 700)
        grouped = case.inputs.data.groupby("treatment").success.agg(["sum", "count"])
        self.assertEqual(grouped.loc["Open surgery", "sum"], 273)
        self.assertEqual(grouped.loc["Percutaneous nephrolithotomy", "sum"], 289)
        self.assertEqual(grouped["count"].to_list(), [350, 350])
        for key in ("source_title", "authors", "year", "doi", "observational_caution"):
            self.assertTrue(case.metadata[key])
        audit = audit_claim(case.inputs.data, {"claim_type": "comparison", "original_claim": case.inputs.claim}, case.inputs.mapping)
        inv = investigate_segments(case.inputs.data, {"claim_type": "comparison"}, audit,
                                   case.inputs.mapping, "stone_size", True)
        self.assertEqual(audit["status"], "Supported")
        self.assertEqual(inv["finding"], "direction_reversal")
        self.assertTrue(all(row["change"] < 0 for row in inv["segment_results"]))

    def test_semantic_cases_frozen_and_no_gold_mapping_leak(self):
        first, second = semantic_cases(), semantic_cases()
        self.assertEqual(len(first), 7)
        for a, b in zip(first, second):
            self.assertTrue(a.inputs.data.equals(b.inputs.data))
            self.assertEqual(a.metadata, b.metadata)
            self.assertEqual(a.inputs.mapping, {})
            self.assertFalse(hasattr(a.inputs, "expected_interpretation"))

    def test_rules_can_map_simple_alias_and_ask_on_ambiguity(self):
        cases = semantic_cases()
        clear = rules_interpret(cases[0].inputs)
        self.assertEqual(clear["metric_column"], "conv_pct")
        self.assertEqual(clear["left"], "2026-03")
        self.assertFalse(clear["needs_confirmation"])
        ambiguous = predict_semantic(cases[4].inputs, "rules_only")
        self.assertEqual(ambiguous["execution_status"], "mapping_required")
        self.assertIsNone(ambiguous["predicted_status"])

    def test_mapping_required_excluded_from_analytical_failure(self):
        case = semantic_cases()[4]
        prediction = predict_semantic(case.inputs, "rules_only")
        row = score_row(case.metadata, prediction, "rules_only")
        summary = summarize([row])
        self.assertEqual(summary["attempted"], 0)
        self.assertEqual(summary["mapping_required"], 1)
        interpretation = interpretation_metrics([row])
        self.assertEqual(interpretation["counts"]["correct_tool_selection"], [1, 1])
        self.assertEqual(interpretation["counts"]["end_to_end_final_status_accuracy"], [0, 1])

    def test_semantic_runner_separates_interpretation_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_benchmark("semantic", "rules_only", tmp)
            self.assertEqual(report["case_count"], 7)
            self.assertIn("interpretation", report["variants"]["rules_only"])


if __name__ == "__main__":
    unittest.main()
