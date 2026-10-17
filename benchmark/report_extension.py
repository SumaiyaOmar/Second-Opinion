"""Combine saved extension runs without rerunning models or analytical rules."""

import hashlib
import json
from pathlib import Path


def write_report(root="benchmark/results/extension_v1"):
    root = Path(root)
    summaries = {split: json.loads((root / split / "summary.json").read_text(encoding="utf-8"))
                 for split in ("held_out", "real_documented", "semantic")}
    rows = {split: json.loads((root / split / "results.json").read_text(encoding="utf-8")) for split in summaries}
    hashes = json.loads((root / "preserved_results_sha256.json").read_text(encoding="utf-8"))
    preserved = all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    lines = ["# Documented and semantic extension v1", "",
             f"Original result artifacts unchanged: {preserved} ({len(hashes)} files).",
             "No thresholds were tuned on these cases. Development results are not independent evidence.", "",
             "## Final-status accuracy across splits", "",
             "| Variant | Held-out synthetic | Documented kidney-stone | Semantic end-to-end |",
             "|---|---:|---:|---:|"]
    for variant in summaries["semantic"]["variants"]:
        values = [summaries[split]["variants"][variant]["metric_counts"]["final_status_accuracy"] for split in ("held_out", "real_documented")]
        values.append(summaries["semantic"]["variants"][variant]["interpretation"]["counts"]["end_to_end_final_status_accuracy"])
        lines.append(f"| {variant} | " + " | ".join(f"{n}/{d}" for n, d in values) + " |")
    lines.extend(["", "## Semantic interpretation", "",
        "Exact matches; API/malformed responses are incorrect. Mapping-required cases have no final verdict, are excluded from conditional analytical accuracy, and remain unresolved in end-to-end accuracy.", "",
        "| Variant | Claim type | Metric | Time/buckets | Segment/confirmation | Recommended tools | End-to-end |",
        "|---|---:|---:|---:|---:|---:|---:|"])
    for variant, summary in summaries["semantic"]["variants"].items():
        lines.append(f"| {variant} | " + " | ".join(f"{n}/{d}" for n, d in summary["interpretation"]["counts"].values()) + " |")
    lines.extend(["", "## Mapping required", ""])
    for variant, summary in summaries["semantic"]["variants"].items():
        lines.append(f"- {variant}: {', '.join(summary['interpretation']['mapping_required_cases']) or 'none'}")
    lines.extend(["", "## Full-system failures and unresolved cases", ""])
    for split, split_rows in rows.items():
        for row in split_rows:
            if row["variant"] != "full":
                continue
            mismatches = []
            expected_interpretation = row["expected"].get("expected_interpretation")
            if expected_interpretation:
                actual = row["prediction"].get("interpretation") or {}
                for key, expected in expected_interpretation.items():
                    observed = actual.get(key)
                    equal = set(observed or []) == set(expected) if key == "tool_selection" else observed == expected
                    if not equal:
                        mismatches.append(key)
            if not row["correct"] or row["driver_correct"] is False or not row["error_type_correct"] or mismatches:
                lines.append(f"- {split}/{row['case_id']}: execution={row['prediction']['execution_status']}; "
                             f"expected={row['expected']['expected_status']}; predicted={row['prediction']['predicted_status']}; "
                             f"interpretation mismatches={mismatches}; error label correct={row['error_type_correct']}.")
    lines.extend(["", "## Documented-case caution and limitations", "",
        "Source: Charig et al., BMJ 1986, DOI 10.1136/bmj.292.6524.879, PMID 3083922. "
        "Publisher metadata/aggregate counts checked; stone-size cells supplied explicitly by the user and corroborated by the cited teaching transcription. "
        "The input is observational count data, anonymously expanded into binary outcomes; no treatment's causal superiority is established.",
        "The unchanged correction template can use temporal 'declined' for non-temporal treatment contrasts. "
        "The unchanged pooled-IQR rule can remove valid binary failures. Both are documented limitations, not reasons to tune this evaluation.",
        "One documented example and seven synthetic semantic cases are too few for broad claims. "
        "Semantic recommended-tool accuracy is not executed-tool accuracy; no-Critic still omits Critic. "
        "A fixed mean/greater scaffold means aggregation/operator interpretation is not evaluated. "
        "Conditional accuracy must be read with mapping coverage and end-to-end accuracy. "
        "See each split's JSON/CSV for every variant's failures and source hashes."])
    path = root / "REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_report())
