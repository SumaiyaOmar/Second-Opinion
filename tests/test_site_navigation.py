"""Website chrome, saved evidence and upload accessibility regressions."""

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class SiteNavigationTests(unittest.TestCase):
    def test_anchors_sections_and_placeholder_available_without_upload(self):
        app = AppTest.from_string("from app import main\nmain()").run(timeout=30)
        self.assertFalse(app.exception)
        html = " ".join(n.value for n in app.markdown)
        for anchor in ("home-section", "how-it-works-section", "try-it-section", "benchmark-evidence-section", "about-section", "github-repository"):
            self.assertIn(f'href="#{anchor}"', html)
            self.assertIn(f'id="{anchor}"', html)
        self.assertIn('aria-label="Main navigation"', html)
        self.assertIn('target="_self"', html)
        self.assertIn("Public repository URL coming soon.", html)
        for title in ("Interpret the claim", "Map the data", "Verify the numbers", "Look for hidden patterns",
                      "Challenge the conclusion", "Return a verdict"):
            self.assertIn(title, html)
        self.assertTrue(any(e.label == "View frozen benchmark artifacts" and not e.proto.expanded for e in app.expander))

    def test_evidence_displays_saved_run_and_caveats(self):
        app = AppTest.from_string("from ui.site import information_sections\ninformation_sections()").run()
        self.assertFalse(app.exception)
        html = " ".join(n.value for n in app.markdown)
        self.assertIn("11/12", html)
        self.assertIn("Correct automatic mappings</dt><dd>7", html)
        self.assertIn("Incorrect automatic mappings</dt><dd>0", html)
        table = app.table[0].value
        self.assertEqual(list(table.iloc[:, 1]), ["5/12", "0/12", "9/12"])
        self.assertTrue(any("Critic can over-abstain" in item.value for item in app.info))
        self.assertTrue(any("does not prove broad real-world superiority" in item.value for item in app.info))

    def test_upload_styles_cover_normal_hover_focus_and_children(self):
        css = (ROOT / "ui/theme.css").read_text(encoding="utf-8")
        for selector in ('[data-testid="stFileUploader"] button {',
                         '[data-testid="stFileUploader"] button:hover',
                         '[data-testid="stFileUploader"] button:focus-visible',
                         '[data-testid="stFileUploader"] button p',
                         '[data-testid="stFileUploader"] button svg'):
            self.assertIn(selector, css)
        self.assertIn("background: #3049ee !important; color: #fff !important", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("position: sticky", css)

    def test_information_sections_preserve_analysis_state_and_results(self):
        path = ROOT / "benchmark/results/semantic_final_v1/IMMUTABILITY.json"
        import hashlib
        seal = json.loads(path.read_text())
        with patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(b"metric\n12\n")):
            app = AppTest.from_string("from app import main\nmain()")
            app.session_state["navigation_test_marker"] = {"claim": "unchanged"}
            app.run(timeout=30)
            app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["navigation_test_marker"], {"claim": "unchanged"})
        for name, digest in seal["sha256"].items():
            self.assertEqual(hashlib.sha256((path.parent / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
