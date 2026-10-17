"""Targeted regressions from the documented mapper-v1 failures; no scoring."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from core.schema_mapper import map_schema, schema_profile, validate_mapping


CLAIM = "Average conversion rose in March compared with February."
EXTRACTED = {"claim_type": "comparison", "metric": "conversion", "entities_or_segments": []}


def proposal():
    return dict(metric_column="conv_pct", time_column="wave", baseline_bucket="2026-02",
        comparison_bucket="2026-03", segment_column="grp", aggregation="mean",
        candidate_alternatives=[], needs_confirmation=False, ambiguities=[],
        reasoning_summary="No segment selected; the comparison is 2099-12 using invented_column.")


class MapperReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({"wave": ["2026-02"] * 4 + ["2026-03"] * 4,
            "grp": ["A", "A", "B", "B"] * 2, "conv_pct": [10] * 4 + [20] * 4})

    def recover(self, output=None, claim=CLAIM, **options):
        return validate_mapping(output if output is not None else proposal(), self.data, claim, EXTRACTED,
            schema_profile(self.data, list(self.data.columns)), recover=True, **options)

    def test_unrequested_segment_removed_without_new_confirmation(self):
        result = self.recover()
        self.assertIsNone(result["segment_column"])
        self.assertEqual(result["field_validity"]["segment_column"]["status"], "not_required")
        self.assertFalse(result["needs_confirmation"])

    def test_explicit_segment_preserved(self):
        result = self.recover(claim=CLAIM + " Compare within each cohort.")
        self.assertEqual(result["segment_column"], "grp")
        self.assertIn("segment_column = 'grp'", result["reasoning_summary"])
        self.assertNotIn("No segment selected", result["reasoning_summary"])

    def test_upstream_or_user_can_request_segment(self):
        for option in ("upstream_requires_segmentation", "user_confirmed_segment"):
            self.assertEqual(self.recover(**{option: True})["segment_column"], "grp")

    def test_user_confirmation_resolves_segment_alternatives(self):
        self.data["region"] = ["N", "S"] * 4
        output = proposal()
        output["candidate_alternatives"] = [{"role": "segment", "column": column} for column in ("grp", "region")]
        result = self.recover(output, user_confirmed_segment=True)
        self.assertEqual(result["segment_column"], "grp")
        self.assertNotIn("segment_column", result["confirmation_fields"])

    def test_time_survives_ambiguous_metric(self):
        self.data["retention_pct"] = self.data.conv_pct
        output = proposal()
        output["segment_column"] = None
        result = self.recover(output, claim="Average performance rose in March compared with February.")
        self.assertIsNone(result["metric_column"])
        self.assertEqual(result["time_column"], "wave")
        self.assertEqual(result["baseline_bucket"], "2026-02")
        self.assertEqual(result["comparison_bucket"], "2026-03")
        self.assertEqual(result["confirmation_fields"], ["metric_column"])

    def test_metric_survives_ambiguous_segment(self):
        self.data["region"] = ["N", "S"] * 4
        result = self.recover(claim=CLAIM + " Compare across groups.")
        self.assertEqual(result["metric_column"], "conv_pct")
        self.assertEqual(result["confirmation_fields"], ["segment_column"])
        self.assertIsNone(result["segment_column"])

    def test_one_invalid_bucket_preserves_valid_siblings(self):
        output = proposal()
        output["comparison_bucket"] = "2099-12"
        result = self.recover(output)
        self.assertEqual(result["confirmation_fields"], ["comparison_bucket"])
        self.assertEqual(result["baseline_bucket"], "2026-02")
        self.assertEqual(result["metric_column"], "conv_pct")
        self.assertIsNone(result["comparison_bucket"])
        self.assertNotIn("2099-12", result["reasoning_summary"])
        self.assertTrue(any(d["reason"] == "candidate_validation_failure" for d in result["internal_diagnostics"]))

    def test_rejected_column_never_appears_in_rationale(self):
        output = proposal()
        output["metric_column"] = "invented_column"
        result = self.recover(output)
        self.assertEqual(result["confirmation_fields"], ["metric_column"])
        self.assertNotIn("invented_column", result["reasoning_summary"])
        self.assertEqual(result["time_column"], "wave")

    def test_field_local_model_uncertainty(self):
        output = proposal()
        output.update(segment_column=None, needs_confirmation=True, uncertain_fields=["metric_column"],
                      ambiguities=["The metric and time might be unclear (untrusted prose)."])
        result = self.recover(output)
        self.assertEqual(result["confirmation_fields"], ["metric_column"])
        self.assertEqual(result["field_validity"]["time_column"]["status"], "valid")

    @patch("core.schema_mapper.get_nebius_client", side_effect=RuntimeError("PRIVATE_PROVIDER_SECRET"))
    def test_transport_failure_recovers_time_and_aggregation(self, factory):
        result = map_schema(CLAIM, EXTRACTED, self.data)
        self.assertEqual(result["time_column"], "wave")
        self.assertEqual(result["baseline_bucket"], "2026-02")
        self.assertEqual(result["comparison_bucket"], "2026-03")
        self.assertEqual(result["aggregation"], "mean")
        self.assertEqual(result["confirmation_fields"], ["metric_column"])
        self.assertEqual(result["internal_diagnostics"][0]["reason"], "provider_error")
        self.assertNotIn("PRIVATE_PROVIDER_SECRET", json.dumps(result))

    @patch("core.schema_mapper.get_nebius_client")
    def test_malformed_output_recovers_known_fields(self, factory):
        factory.return_value.__enter__.return_value.chat.completions.create.return_value.choices[0].message.content = "not JSON: PRIVATE_PROVIDER_SECRET"
        result = map_schema(CLAIM, EXTRACTED, self.data)
        self.assertEqual(result["time_column"], "wave")
        self.assertEqual(result["internal_diagnostics"][0]["reason"], "malformed_output")
        self.assertNotIn("PRIVATE_PROVIDER_SECRET", json.dumps(result))

    def test_partial_schema_retains_valid_fields(self):
        result = self.recover({"metric_column": "conv_pct", "time_column": "wave"})
        self.assertEqual(result["metric_column"], "conv_pct")
        self.assertEqual(result["comparison_bucket"], "2026-03")
        self.assertEqual(result["aggregation"], "mean")
        self.assertTrue(any(d["reason"] == "schema_validation_failure" for d in result["internal_diagnostics"]))

    def test_former_held_out_gold_and_data_preserved_as_development(self):
        import hashlib
        from benchmark.semantic_held_out import held_out_cases
        frozen = json.loads((Path(__file__).resolve().parents[1] / "benchmark/frozen/semantic_held_out_v1.json").read_text())
        for current, old in zip(held_out_cases(), frozen["cases"]):
            self.assertEqual(current.metadata["evaluation_role"], "development")
            for field in ("case_id", "expected_status", "expected_error_type", "expected_driver", "should_abstain", "is_clean_control", "generation_seed", "expected_interpretation"):
                self.assertEqual(current.metadata[field], old["metadata"][field])
            self.assertEqual(hashlib.sha256(current.inputs.data.to_json(orient="records").encode()).hexdigest(), old["records_sha256"])

    def test_new_final_set_is_deterministic_and_distinct(self):
        from benchmark.semantic_final_held_out import final_held_out_cases
        from benchmark.semantic_held_out import held_out_cases
        first, second = final_held_out_cases(), final_held_out_cases()
        self.assertEqual(len(first), 12)
        self.assertTrue({c.metadata["generation_seed"] for c in first}.isdisjoint(c.metadata["generation_seed"] for c in held_out_cases()))
        old_columns = {column for c in held_out_cases() for column in c.inputs.data.columns}
        new_columns = {column for c in first for column in c.inputs.data.columns}
        self.assertTrue(old_columns.isdisjoint(new_columns))
        for a, b in zip(first, second):
            self.assertEqual(a.metadata, b.metadata)
            self.assertTrue(a.inputs.data.equals(b.inputs.data))


if __name__ == "__main__":
    unittest.main()
