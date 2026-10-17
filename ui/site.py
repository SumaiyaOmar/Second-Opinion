"""Single-page navigation and read-only project information."""

import json
from pathlib import Path

import streamlit as st

from ui.reveals import text


RESULTS = Path(__file__).resolve().parents[1] / "benchmark/results/semantic_final_v1"


def navigation():
    with st.container(key="site_nav"):
        st.markdown('''<nav class="so-navbar" aria-label="Main navigation">
<a class="so-wordmark" href="#home-section" target="_self"><span aria-hidden="true">so.</span> Second Opinion</a>
<div class="so-nav-links">
<a href="#home-section" target="_self">Home</a>
<a href="#how-it-works-section" target="_self">How it works</a>
<a href="#try-it-section" target="_self">Try it</a>
<a href="#benchmark-evidence-section" target="_self">Evidence</a>
<a href="#about-section" target="_self">About</a>
<a class="so-github" href="#github-repository" target="_self" aria-label="GitHub repository — public URL coming soon">GitHub ↗</a>
</div></nav>''', unsafe_allow_html=True)


def workflow():
    steps = (("Claim", "Interpret the claim"), ("Map", "Map the data"),
             ("Audit", "Verify the numbers"), ("Investigate", "Look for hidden patterns"),
             ("Stress-test", "Challenge the conclusion"), ("Verdict", "Return a verdict"))
    st.markdown('<section id="how-it-works-section" class="so-site-section"><span class="so-eyebrow">How it works</span>'
                '<h2>A second look, at every step.</h2><ol class="so-workflow">' + ''.join(
                    f'<li><span class="so-step-number">{i}</span><h3>{title}</h3><p>{description}</p></li>'
                    for i, (title, description) in enumerate(steps, 1)) + '</ol></section>', unsafe_allow_html=True)


def information_sections():
    st.markdown('<div id="benchmark-evidence-section" class="so-section-anchor"></div>', unsafe_allow_html=True)
    with st.container(border=True, key="site_evidence"):
        st.subheader("Evidence", anchor="benchmark-evidence-heading")
        st.caption("One frozen evaluation. Reported with its limitations.")
        try:
            summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
            mappings = json.loads((RESULTS / "mapping_counts.json").read_text(encoding="utf-8"))
            full = summary["variants"]["full"]["interpretation"]["counts"]
            def ratio(variant, metric):
                n, d = summary["variants"][variant]["interpretation"]["counts"][metric]
                return f"{n}/{d}"
            items = [
                ("Final held-out cases", str(summary["case_count"])),
                ("Full: metric mapping", ratio("full", "metric_column_mapping_accuracy")),
                ("Full: time/bucket mapping", ratio("full", "time_bucket_mapping_accuracy")),
                ("Correct automatic mappings", str(mappings["full"]["correct_automatic_mappings"])),
                ("Correct confirmation requests", str(mappings["full"]["correct_confirmation_requests"])),
                ("Incorrect automatic mappings", str(mappings["full"]["incorrect_automatic_mappings"])),
            ]
            st.markdown('<dl class="so-benchmark-facts">' + ''.join(
                f'<div><dt>{text(title)}</dt><dd>{text(value)}</dd></div>' for title, value in items) + '</dl>',
                unsafe_allow_html=True)
            st.table({"End-to-end status accuracy": ["Full system", "Rules-only", "Model + tools, no Critic"],
                      "Correct / 12 cases": [ratio(v, "end_to_end_final_status_accuracy") for v in ("full", "rules_only", "no_critic")]})
            st.info("Small synthetic held-out evaluation; it does not prove broad real-world superiority. "
                    "Critic can over-abstain. Correct confirmation routing is not a completed final verdict.")
            with st.expander("View frozen benchmark artifacts", expanded=False):
                st.caption("Saved final run: benchmark/results/semantic_final_v1. No evaluation is run by this page.")
                for filename, label, mime in (("REPORT.md", "Download detailed report", "text/markdown"),
                                               ("results.json", "Download per-case results", "application/json")):
                    st.download_button(label, (RESULTS / filename).read_bytes(), file_name=filename,
                                       mime=mime, on_click="ignore", key="artifact_" + filename)
        except (OSError, ValueError, KeyError, TypeError):
            st.info("The saved evaluation summary is unavailable. No benchmark has been rerun.")

    st.markdown('''<section id="about-section" class="so-site-section so-about">
<span class="so-eyebrow">About / methodology</span>
<h2>AI interpretation. Reproducible calculations.</h2>
<p>Second Opinion is an AI-assisted analytics review tool. NVIDIA Nemotron-3.5-Lightning, served through
Nebius Token Factory, supports interpretation, tool selection, and explanation. Deterministic Python
performs the calculations.</p><p>The system is designed to show uncertainty rather than invent confidence.
Evidence, limitations, and computational receipts remain available for review.</p></section>
<footer class="so-footer"><strong>Second Opinion</strong>
<span>Built with Nebius Token Factory + NVIDIA Nemotron</span>
<a href="#github-repository" target="_self">GitHub ↗</a>
<span id="github-repository">Public repository URL coming soon.</span></footer>''', unsafe_allow_html=True)
