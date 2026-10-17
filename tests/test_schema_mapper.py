"""Role constraints, validation, ambiguity, privacy and graceful manual fallback."""

import copy
import json
import unittest
from unittest.mock import patch

import pandas as pd

from core.schema_mapper import map_schema, schema_profile, validate_mapping, bucket_candidates
from benchmark.semantic import semantic_cases
from benchmark.semantic_held_out import held_out_cases


CLAIM = "Average conversion rose in March compared with February within each cohort."
EXTRACTED = {"claim_type": "comparison", "metric": "conversion"}


def proposal():
    return dict(metric_column="conv_pct", time_column="wave", baseline_bucket="2026-02", comparison_bucket="2026-03",
                segment_column="grp", aggregation="mean", candidate_alternatives=[], needs_confirmation=False,
                ambiguities=[], reasoning_summary="Calendar values identify wave; conv_pct is numeric and grp contains cohort labels.")


class SchemaMapperTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({"wave": ["2026-02"] * 4 + ["2026-03"] * 4,
                                  "grp": ["A", "A", "B", "B"] * 2, "conv_pct": [10] * 4 + [20] * 4})
        self.profile = schema_profile(self.data, list(self.data.columns))

    def validate(self, output=None, claim=CLAIM):
        return validate_mapping(output or proposal(), self.data, claim, EXTRACTED, self.profile)

    def test_obvious_renamed_metric(self):
        self.assertEqual(self.validate()["metric_column"], "conv_pct")
        self.assertFalse(self.validate()["needs_confirmation"])

    def test_renamed_time_column(self):
        self.assertEqual(self.validate()["time_column"], "wave")

    def test_natural_language_bucket_mapping(self):
        self.assertEqual(bucket_candidates(CLAIM, ["2026-02", "2026-03"]), ("2026-02", "2026-03"))
        reversed_proposal = proposal()
        reversed_proposal.update(baseline_bucket="2026-03", comparison_bucket="2026-02")
        self.assertTrue(self.validate(reversed_proposal)["needs_confirmation"])

    def test_renamed_segment_field(self):
        self.assertEqual(self.validate()["segment_column"], "grp")

    def test_two_plausible_segments_require_confirmation(self):
        self.data["region"] = ["N", "S"] * 4
        self.profile = schema_profile(self.data, list(self.data.columns))
        output = self.validate(claim="Average conversion rose in March compared with February across customer groups.")
        self.assertTrue(output["needs_confirmation"])
        self.assertIsNone(output["segment_column"])
        self.assertEqual({a["column"] for a in output["candidate_alternatives"]}, {"grp", "region"})

    def test_nonexistent_column_rejected(self):
        output = proposal()
        output["metric_column"] = "invented"
        with self.assertRaises(ValueError):
            self.validate(output)

    def test_nonexistent_bucket_rejected(self):
        output = proposal()
        output["comparison_bucket"] = "2099-12"
        with self.assertRaises(ValueError):
            self.validate(output)

    def test_nonnumeric_metric_rejected(self):
        output = proposal()
        output["metric_column"] = "grp"
        with self.assertRaises(ValueError):
            self.validate(output)

    @patch("core.schema_mapper.get_nebius_client", side_effect=RuntimeError("private credential detail"))
    def test_model_failure_manual_fallback(self, factory):
        output = map_schema(CLAIM, EXTRACTED, self.data)
        self.assertTrue(output["needs_confirmation"])
        self.assertIsNone(output["metric_column"])
        self.assertNotIn("private credential detail", json.dumps(output))

    @patch("core.schema_mapper.get_nebius_client")
    def test_model_is_given_role_specific_existing_candidates(self, factory):
        create = factory.return_value.__enter__.return_value.chat.completions.create
        create.return_value.choices[0].message.content = json.dumps(proposal())
        output = map_schema(CLAIM, EXTRACTED, self.data, ["grp"])
        self.assertFalse(output["needs_confirmation"])
        properties = create.call_args.kwargs["response_format"]["json_schema"]["schema"]["properties"]
        self.assertEqual(properties["metric_column"]["enum"], [None, "conv_pct"])
        self.assertEqual(properties["time_column"]["enum"], [None, "wave"])
        self.assertNotIn("2099-12", properties["comparison_bucket"]["enum"])

    def test_small_segments_cannot_silently_pass(self):
        self.data = self.data.drop(index=0)
        self.profile = schema_profile(self.data, list(self.data.columns))
        self.assertTrue(self.validate()["needs_confirmation"])

    def test_sensitive_or_unapproved_values_withheld(self):
        self.data["email"] = "private@example.invalid"
        profile = schema_profile(self.data, ["email"])
        self.assertNotIn("private@example.invalid", json.dumps(profile))
        self.assertEqual(next(c for c in profile["columns"] if c["name"] == "grp")["values"], [])

    def test_old_cases_development_new_seeds_disjoint(self):
        dev, held = semantic_cases(), held_out_cases()
        self.assertTrue(all(c.metadata["evaluation_role"] == "development" for c in dev))
        self.assertEqual(len(held), 7)
        self.assertTrue({c.metadata["generation_seed"] for c in dev}.isdisjoint(c.metadata["generation_seed"] for c in held))
        for a, b in zip(held, held_out_cases()):
            self.assertEqual(a.metadata, b.metadata)
            self.assertTrue(a.inputs.data.equals(b.inputs.data))
