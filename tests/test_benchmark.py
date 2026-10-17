"""Reproducible splits, label isolation, metrics, CLI and safe persisted output."""

import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark.cases import generated_cases, load_documented_cases, SEEDS
from benchmark.metrics import score_row, summarize
from benchmark.run import main, run_benchmark
from benchmark.variants import predict


def prediction(status="Supported", error=None, driver=None, execution="completed"):
    return dict(predicted_status=status, detected_error_type=error, predicted_driver=driver,
                execution_status=execution, abstained=status == "Inconclusive", failure=None)


class BenchmarkTests(unittest.TestCase):
    def test_generation_is_deterministic(self):
        first, second = generated_cases("development"), generated_cases("development")
        self.assertEqual(len(first), 6)
        for a, b in zip(first, second):
            self.assertEqual(a.metadata, b.metadata)
            self.assertTrue(a.inputs.data.equals(b.inputs.data))

    def test_seeds_and_ids_do_not_overlap(self):
        self.assertTrue(set(SEEDS["development"]).isdisjoint(SEEDS["held_out"]))
        dev, held = generated_cases("development"), generated_cases("held_out")
        self.assertTrue({c.metadata["case_id"] for c in dev}.isdisjoint(c.metadata["case_id"] for c in held))
        self.assertTrue(all(c.metadata["split"] == "held_out" for c in held))

    def test_labels_cannot_enter_predictions(self):
        case = generated_cases("development")[0]
        before = copy.deepcopy(case.inputs)
        self.assertNotIn("expected_status", vars(case.inputs))
        with patch("benchmark.run.predict", return_value=prediction()) as predictor, tempfile.TemporaryDirectory() as tmp:
            run_benchmark(output=tmp)
            self.assertTrue(all(set(vars(call.args[0])) == {"data", "claim", "mapping", "segment_column"} for call in predictor.call_args_list))
        first = predict(case.inputs, "rules_only")
        case.metadata["expected_status"] = "Unsupported"
        second = predict(case.inputs, "rules_only")
        self.assertEqual(first["predicted_status"], second["predicted_status"])
        self.assertTrue(case.inputs.data.equals(before.data))

    def test_metric_calculations_false_alarms_and_abstention(self):
        cases = {c.metadata["case_type"]: c for c in generated_cases("development")}
        rows = [
            score_row(cases["clean"].metadata, prediction("Partially supported", "outlier"), "test"),
            score_row(cases["insufficient"].metadata, prediction("Inconclusive", "insufficient"), "test"),
            score_row(cases["simpson"].metadata, prediction("Partially supported", "simpson", "mix_effect"), "test"),
        ]
        result = summarize(rows)
        self.assertEqual(result["metrics"]["error_detection_rate"], 1)
        self.assertEqual(result["metrics"]["false_alarm_rate"], 1)
        self.assertEqual(result["metrics"]["final_status_accuracy"], 2 / 3)
        self.assertEqual(result["metrics"]["correct_abstention_rate"], 1)
        self.assertEqual(result["metrics"]["rank1_driver_accuracy"], 1)
        self.assertEqual(result["per_error_class_accuracy"]["clean"]["accuracy"], 0)

    def test_runtime_error_is_not_a_correct_abstention(self):
        case = generated_cases("development")[4]
        row = score_row(case.metadata, prediction("Inconclusive", execution="error"), "test")
        summary = summarize([row])
        self.assertEqual(summary["metrics"]["correct_abstention_rate"], 0)
        self.assertFalse(row["correct"])

    def test_unrun_models_do_not_get_fake_scores(self):
        case = generated_cases("development")[0]
        for variant in ("plain", "no_critic", "full"):
            result = predict(case.inputs, variant, live=False)
            self.assertEqual(result["execution_status"], "not_run")
            summary = summarize([score_row(case.metadata, result, variant)])
            self.assertIsNone(summary["metrics"]["final_status_accuracy"])

    def test_runner_cli_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            main(["--split", "development", "--variant", "all", "--output", tmp])
            root = Path(tmp)
            self.assertTrue(all((root / file).is_file() for file in ("results.csv", "results.json", "summary.md", "summary.json")))
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(report["case_count"], 6)
            self.assertEqual(len(report["variants"]), 4)
            self.assertEqual(report["variants"]["plain"]["not_run"], 6)
            self.assertIn("failures", report["variants"]["rules_only"])

    @patch("benchmark.variants.get_nebius_client", side_effect=RuntimeError("FAKE_SECRET_CREDENTIAL"))
    def test_no_credentials_written_even_on_provider_error(self, factory):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NEBIUS_API_KEY": "FAKE_SECRET_CREDENTIAL"}):
            report = run_benchmark(variant="plain", output=tmp, live=True)
            self.assertEqual(report["variants"]["plain"]["execution_errors"], 6)
            for path in Path(tmp).iterdir():
                self.assertNotIn("FAKE_SECRET_CREDENTIAL", path.read_text(encoding="utf-8"))
                self.assertNotIn("NEBIUS_API_KEY", path.read_text(encoding="utf-8"))

    def test_documented_loader_requires_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text("[]")
            self.assertEqual(load_documented_cases(manifest), [])
            manifest.write_text('[{"metadata": {}}]')
            with self.assertRaises(ValueError):
                load_documented_cases(manifest)


if __name__ == "__main__":
    unittest.main()
