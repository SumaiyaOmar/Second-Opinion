"""Presentation regressions without provider calls or benchmark scoring."""

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
from core.critic import run_critic
from core.investigator import investigate_segments
from core.verdict import generate_verdict


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = (ROOT / "data/synthetic_simpson.csv").read_bytes()
CLAIM = dict(original_claim="The overall score increased after the change.",
             claim_type="comparison", metric="score")
MAPPING = dict(confirmed=True, calculation_type="two_periods", metric="score", aggregation="mean",
               operator="greater", group_column="period", left="after", right="before")


def seeded_app(results=False):
    app = AppTest.from_string("from app import main\nmain()")
    app.session_state["dataset_id"] = hashlib.sha256(PAYLOAD).hexdigest()
    app.session_state["extracted_claim"] = CLAIM
    app.session_state["claim_input"] = CLAIM["original_claim"]
    if results:
        data = pd.read_csv(io.BytesIO(PAYLOAD))
        audit = audit_claim(data, CLAIM, MAPPING)
        inv = investigate_segments(data, CLAIM, audit, MAPPING, "segment", True)
        critic = run_critic(data, CLAIM, audit, MAPPING)
        verdict = generate_verdict(CLAIM, audit, inv, critic, use_model=False)
        for key, value in dict(audit_mapping=MAPPING, audit_result=audit, investigation_result=inv,
                               critic_result=critic, verdict_result=verdict).items():
            app.session_state[key] = value
    return app


def walk(node, ancestors=()):
    yield node, ancestors
    for child in getattr(node, "children", {}).values():
        yield from walk(child, ancestors + (node,))


class PresentationTests(unittest.TestCase):
    def test_styled_reveals_use_existing_evidence_and_escape_text(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app(True).run(timeout=30)
        self.assertFalse(app.exception)
        rendered = " ".join(n.value for n in app.markdown)
        for value in ("36 → 74", "90 → 80", "30 → 20", "10% high", "90% high",
                      "But every segment declined.", "PARTIALLY SUPPORTED",
                      "What changed", "What contradicts it", "Why it happened", "Stability"):
            self.assertIn(value, rendered)
        self.assertIn("so-verdict-badge", rendered)
        self.assertIn("Hidden pattern checked", rendered)
        self.assertIn("#3049ee", rendered)
        self.assertTrue(any(b.label == "Upload data" for b in app.button))

    def test_hero_is_illustrative_until_real_values_are_available(self):
        app = AppTest.from_string('from ui.story import hero_visual\nhero_visual()').run()
        rendered = " ".join(n.value for n in app.markdown)
        self.assertIn("Illustrative demo", rendered)
        self.assertIn("THE HEADLINE", rendered)
        self.assertIn("WAIT A SECOND", rendered)
        app = AppTest.from_string('from ui.story import hero_visual\nhero_visual({"computed_values":{"right":12,"left":19}}, has_dataset=True)').run()
        rendered = " ".join(n.value for n in app.markdown)
        self.assertIn("19<small>baseline 12", rendered)
        self.assertNotIn("Illustrative demo", rendered)
        self.assertNotIn(">74<", rendered)

    def test_six_progress_stages_do_not_fake_completion(self):
        source = '''from ui.reveals import progress
progress(extracted={"original_claim":"test"}, mapping={"confirmed":False})
'''
        app = AppTest.from_string(source).run()
        rendered = " ".join(n.value for n in app.markdown)
        self.assertEqual(rendered.count('class="so-stage-pill complete"'), 1)
        self.assertEqual(rendered.count('class="so-stage-pill pending"'), 5)
        for title in ("Claim interpreted", "Mapping confirmed", "Numbers checked", "Hidden pattern checked", "Stress tested", "Verdict ready"):
            self.assertIn(title, rendered)

    def test_reference_chart_types_preserve_all_calculated_records(self):
        import copy
        from tools.visuals import evidence_charts
        from ui.evidence import show_chart
        data = pd.read_csv(io.BytesIO(PAYLOAD))
        audit = audit_claim(data, CLAIM, MAPPING)
        inv = investigate_segments(data, CLAIM, audit, MAPPING, "segment", True)
        charts = evidence_charts(audit, inv)
        for kind in ("aggregate", "segments", "composition"):
            original = copy.deepcopy(charts[kind])
            with patch("ui.evidence.st.vega_lite_chart") as render, patch("ui.evidence.st.caption"):
                show_chart(charts[kind], kind=kind)
            styled = render.call_args.kwargs["spec"]
            self.assertEqual(styled["data"], original["data"])
            self.assertEqual(charts[kind], original)
            if kind == "segments":
                self.assertEqual(styled["mark"]["type"], "line")
            if kind == "composition":
                self.assertEqual(styled["encoding"]["x"]["stack"], "zero")

    def test_no_fabricated_pattern_or_numbers_on_clean_result(self):
        from ui.reveals import text
        self.assertEqual(text('<script>alert("x")</script>'), '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;')
        source = '''from ui.reveals import result_reveals, progress
result_reveals({"metric":"sales", "computed_values":{"right":2,"left":5}}, None)
progress({"status":"Supported"}, None, None)
'''
        app = AppTest.from_string(source).run()
        self.assertFalse(app.exception)
        rendered = " ".join(n.value for n in app.markdown)
        self.assertIn("2 → 5", rendered)
        self.assertNotIn("36 → 74", rendered)
        self.assertNotIn("every segment declined", rendered)
        self.assertNotIn("Hidden pattern found", rendered)
        self.assertNotIn("Stress test complete", rendered)

    def test_chart_styling_does_not_change_data_or_source_spec(self):
        import copy
        from tools.visuals import evidence_charts
        from ui.evidence import show_chart
        chart = evidence_charts(audit_claim(pd.read_csv(io.BytesIO(PAYLOAD)), CLAIM, MAPPING))["aggregate"]
        original = copy.deepcopy(chart)
        with patch("ui.evidence.st.vega_lite_chart") as render, patch("ui.evidence.st.caption"):
            show_chart(chart)
        styled = render.call_args.kwargs["spec"]
        self.assertEqual(styled["data"], original["data"])
        self.assertEqual(chart, original)
        self.assertEqual(styled["encoding"]["color"]["scale"]["range"], ["#3049ee", "#ff6b57"])

    def test_mapping_defaults_on_and_demo_reenables_it(self):
        with patch("app.map_schema", return_value={}) as mapper, patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app().run()
            self.assertTrue(app.toggle[0].value)
            mapper.assert_called_once()
            app.toggle[0].set_value(False).run()
            self.assertFalse(app.toggle[0].value)
            next(b for b in app.button if b.label == "Try demo case").click().run()
            self.assertTrue(app.session_state["suggest_schema_mapping"])
            self.assertEqual(len(app.toggle), 0)  # No mapping stage until Analyze claim.
            mapper.assert_called_once()
            self.assertFalse(app.exception)

    def test_stages_hidden_until_actionable_audit(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app().run()
            self.assertFalse(any(s.value in {"Investigation", "Self-Doubt / Stress Test"} for s in app.subheader))
            app.session_state["audit_result"] = audit_claim(pd.read_csv(io.BytesIO(PAYLOAD)), CLAIM)
            app.run()
            self.assertFalse(any(s.value in {"Investigation", "Self-Doubt / Stress Test"} for s in app.subheader))
            app.session_state["audit_result"] = audit_claim(pd.read_csv(io.BytesIO(PAYLOAD)), CLAIM, MAPPING)
            app.session_state["audit_mapping"] = MAPPING
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any(s.value == "Investigation" for s in app.subheader))
            self.assertFalse(any(s.value == "Self-Doubt / Stress Test" for s in app.subheader))

    def test_landing_and_demo_requires_explicit_analysis(self):
        with patch("app.extract_claim") as extract:
            app = AppTest.from_string("from app import main\nmain()").run()
            text = " ".join(x.value for x in app.markdown)
            self.assertIn("An analyst that doubts itself.", text)
            self.assertIn("Most AI analytics tools answer questions.", text)
            self.assertEqual(app.title[0].value, "Second Opinion")
            next(b for b in app.button if b.label == "Try demo case").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_area[0].value, CLAIM["original_claim"])
            self.assertEqual(app.session_state["dataset_id"], hashlib.sha256(PAYLOAD).hexdigest())
            self.assertTrue(any(b.label == "Analyze claim" for b in app.button))
            self.assertFalse(next(e for e in app.expander if e.label == "Preview dataset").proto.expanded)
            extract.assert_not_called()

    def test_result_precedes_debug_json_and_all_json_is_collapsed(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app(True).run(timeout=30)
        self.assertFalse(app.exception)
        nodes = list(walk(app.main))
        verdict_index = next(i for i, (n, _) in enumerate(nodes)
                             if n.type == "subheader" and "Final verdict:" in n.value)
        json_indices = [i for i, (n, _) in enumerate(nodes) if n.type == "json"]
        self.assertTrue(json_indices)
        self.assertLess(verdict_index, min(json_indices))
        for n, parents in nodes:
            if n.type == "json":
                self.assertTrue(any(p.type == "expander" and not p.proto.expanded for p in parents))
        self.assertTrue(any(e.label == "Show proof: final verdict" for e in app.expander))
        self.assertTrue(any(e.label == "View stress-test details" for e in app.expander))

    def test_manual_mapping_preserves_comparison_semantics(self):
        with patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app().run()
            proposal = dict(metric_column="score", time_column="period", baseline_bucket="before",
                            comparison_bucket="after", segment_column=None, aggregation="mean",
                            needs_confirmation=True, confirmation_fields=["metric_column"])
            app.session_state["schema_mapping_result"] = proposal
            app.run()
            self.assertTrue(any("Metric" in w.value for w in app.warning))
            self.assertTrue(next(e for e in app.expander if e.label == "Review or change mapping").proto.expanded)
            next(s for s in app.selectbox if s.label.startswith("Claimed relationship")).select("greater")
            next(c for c in app.checkbox if c.label.startswith("I confirm these columns")).check()
            next(b for b in app.button if b.label == "Run deterministic audit").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["audit_mapping"]["left"], "after")
            self.assertEqual(app.session_state["audit_mapping"]["right"], "before")
            self.assertEqual(app.session_state["audit_result"]["status"], "Supported")

    def test_failed_check_visible_and_credentials_absent(self):
        data = pd.DataFrame({"period": ["before"]*20+["after"]*20, "score": [5]*20+[1]*19+[1000]})
        audit = audit_claim(data, CLAIM, MAPPING)
        critic = run_critic(data, CLAIM, audit, MAPPING)
        verdict = generate_verdict(CLAIM, audit, critic=critic, use_model=False)
        sentinel = "FAKE_UI_SECRET_NEVER_RENDER"
        with patch.dict(os.environ, {"NEBIUS_API_KEY": sentinel}), patch("app.map_schema", return_value={}), patch("streamlit.file_uploader", side_effect=lambda *a, **k: io.BytesIO(PAYLOAD)):
            app = seeded_app()
            for key, value in dict(audit_mapping=MAPPING, audit_result=audit, critic_result=critic, verdict_result=verdict).items():
                app.session_state[key] = value
            app.run(timeout=30)
        self.assertFalse(app.exception)
        warnings = [(n, parents) for n, parents in walk(app.main) if n.type == "warning" and "Failed:" in n.value]
        self.assertTrue(warnings)
        self.assertTrue(any(not any(p.type == "expander" for p in parents) for n, parents in warnings))
        rendered = " ".join(n.value for n in list(app.markdown)+list(app.json))
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn("NEBIUS_API_KEY", rendered)
        self.assertIn("Outlier-removal check", rendered)

    def test_analytical_sources_unchanged(self):
        baseline = json.loads((ROOT / "ui/analysis_integrity.json").read_text())
        for name, digest in baseline.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
