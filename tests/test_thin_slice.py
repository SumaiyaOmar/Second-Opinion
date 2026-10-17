"""Local checks without network calls or credentials."""

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core.claims import ClaimExtractionError, extract_claim, validate_claim
from tools.analytics import profile_dataset


CLAIM = "Revenue increased last quarter."
EXTRACTED = {
    "original_claim": CLAIM,
    "claim_type": "comparison",
    "metric": "revenue",
    "entities_or_segments": [],
    "time_reference": "last quarter",
    "direction": "increase",
    "needs_calculation": True,
    "notes": "Comparison baseline is unspecified.",
}


class ThinSliceTests(unittest.TestCase):
    def test_profile_missing_values_and_types(self):
        profile = profile_dataset(pd.read_csv(io.StringIO("segment,revenue\nA,10\nB,\n")))
        self.assertEqual((profile["row_count"], profile["column_count"]), (2, 2))
        self.assertEqual(profile["columns"]["column"].to_list(), ["segment", "revenue"])
        self.assertEqual(profile["columns"]["missing_values"].to_list(), [0, 1])
        self.assertEqual(profile["columns"].iloc[1]["dtype"], "float64")

    def test_reject_invalid_schema(self):
        invalid_cases = [
            {**EXTRACTED, "claim_type": "verdict"},
            {**EXTRACTED, "needs_calculation": "true"},
            {**EXTRACTED, "entities_or_segments": "all"},
            {**EXTRACTED, "original_claim": "Changed"},
            {**EXTRACTED, "metric": 42},
            {**EXTRACTED, "extra": "field"},
            {key: value for key, value in EXTRACTED.items() if key != "notes"},
        ]
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid), self.assertRaises(ClaimExtractionError):
                validate_claim(invalid, CLAIM)

    @patch("core.claims.get_nebius_client")
    def test_extraction_and_invalid_json(self, factory):
        create = factory.return_value.__enter__.return_value.chat.completions.create
        create.return_value.choices[0].message.content = json.dumps(EXTRACTED)
        self.assertEqual(extract_claim(CLAIM), EXTRACTED)
        self.assertEqual(create.call_args.kwargs["messages"][1]["content"], CLAIM)
        self.assertEqual(create.call_args.kwargs["model"], "nvidia/Nemotron-3_5-Lightning")
        create.return_value.choices[0].message.content = "not JSON"
        with self.assertRaises(ClaimExtractionError):
            extract_claim(CLAIM)

    @patch("core.claims.get_nebius_client")
    def test_blank_claim_does_not_call_model(self, factory):
        with self.assertRaises(ClaimExtractionError):
            extract_claim("  ")
        factory.assert_not_called()

    @patch("core.claims.get_nebius_client", side_effect=RuntimeError("private provider detail"))
    def test_provider_error_is_sanitized(self, factory):
        with self.assertRaises(ClaimExtractionError) as caught:
            extract_claim(CLAIM)
        self.assertNotIn("private provider detail", str(caught.exception))

    def test_app_initial_render(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Second Opinion")

    @patch("app.extract_claim", return_value=EXTRACTED)
    def test_app_upload_and_extract(self, extract):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **kw: io.BytesIO(b"segment,revenue\nA,10\nB,\n")):
            app = AppTest.from_string("from app import main\nmain()").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("2 rows | 2 columns" in item.value for item in app.caption))
            self.assertEqual(len(app.dataframe), 2)
            app.text_area[0].set_value(CLAIM)
            next(b for b in app.button if b.label == "Analyze claim").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(json.loads(app.json[0].value), EXTRACTED)
            extract.assert_called_once_with(CLAIM)

    def test_app_rejects_empty_csv(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", return_value=io.BytesIO(b"")):
            app = AppTest.from_string("from app import main\nmain()").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.error), 1)


if __name__ == "__main__":
    unittest.main()
