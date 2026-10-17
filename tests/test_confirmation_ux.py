"""Pre-analysis presentation and demo scroll regressions."""

import io
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from test_ui_presentation import CLAIM, PAYLOAD, seeded_app, ROOT


class ConfirmationUXTests(unittest.TestCase):
    def test_demo_requests_one_scroll_and_keeps_illustration(self):
        with patch("ui.interactions.components.html") as html, patch("app.extract_claim") as extract:
            app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
            app.button(key="try_demo_case").click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area[0].value, CLAIM["original_claim"])
            self.assertTrue(any("Demo loaded — click Analyze claim" in i.value for i in app.info))
            self.assertTrue(any('74<small>↑ from 36' in i.value for i in app.markdown))
            html.assert_called_once()
            script = html.call_args.args[0]
            self.assertIn('scrollIntoView({ behavior: "smooth", block: "start" })', script)
            self.assertIn('"smooth"', script)
            self.assertIn('const targetId = "try-it-section"', script)
            self.assertIn('window.parent', script)
            self.assertIn('prefers-reduced-motion', script)
            self.assertEqual(html.call_args.kwargs["height"], 0)
            app.run(timeout=30)
            html.assert_called_once()
            extract.assert_not_called()

    def test_scroll_component_remounts_on_each_new_request(self):
        from ui.interactions import scroll_to_inputs
        with patch("ui.interactions.components.html") as html:
            scroll_to_inputs()
            scroll_to_inputs()
        self.assertNotEqual(html.call_args_list[0].args[0], html.call_args_list[1].args[0])
        self.assertIn('const targetId = "try-it-section"', html.call_args.args[0])
        self.assertNotIn('textarea[aria-label', html.call_args.args[0])

    def test_unsubmitted_audit_is_waiting_not_inconclusive(self):
        proposal = dict(metric_column="score", comparison_bucket="after", baseline_bucket="before",
                        time_column="period", segment_column=None, aggregation=None,
                        confirmation_fields=["comparison_bucket", "baseline_bucket", "aggregation"],
                        needs_confirmation=True,
                        field_validity={"metric_column": {"status":"valid"}, "segment_column":{"status":"not_required"}})
        with patch("app.map_schema", return_value=proposal), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app().run(timeout=30)
        self.assertFalse(app.exception)
        visible = " ".join(x.value for x in list(app.markdown) + list(app.info) + list(app.caption))
        self.assertIn("Waiting for mapping confirmation", visible)
        self.assertNotIn("Number check: Inconclusive", visible)
        self.assertNotIn("No conclusion can be drawn from this calculation.", visible)
        self.assertIn("✓ mapped", visible)
        self.assertIn("Not required / not selected", visible)
        self.assertIn("Optional — no action needed", visible)
        self.assertTrue(next(e for e in app.expander if e.label == "Review or change mapping").proto.expanded)
        self.assertTrue(any(b.label == "Run deterministic audit" for b in app.button))

    def test_banner_contrast_is_explicit(self):
        css = (ROOT / "ui/theme.css").read_text(encoding="utf-8")
        self.assertIn("background: #fff2c9; color: #493508", css)
        self.assertIn('stAlertContentWarning"] p { color: #493508 !important;', css)
        self.assertIn("background: #eaf0ff; color: #172d63", css)


if __name__ == "__main__":
    unittest.main()
