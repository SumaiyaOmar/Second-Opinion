"""Summarize saved mapper evaluations without rerunning models or changing rules."""

import json
from pathlib import Path

from benchmark.freeze_mapper import verify_frozen
from benchmark.semantic import semantic_cases
from benchmark.semantic_held_out import held_out_cases


def mapping_outcomes(rows):
    """Partition full-system cases; correct clarification is separate from a verdict."""
    result = {"correct_automatic_mappings": [], "incorrect_automatic_mappings": [],
              "correct_confirmation_requests": [], "unnecessary_confirmation_requests": [], "execution_errors": []}
    for row in rows:
        if row["variant"] != "full":
            continue
        prediction, gold = row["prediction"], row["expected"]["expected_interpretation"]
        if prediction["execution_status"] == "mapping_required":
            key = "correct_confirmation_requests" if gold["needs_confirmation"] else "unnecessary_confirmation_requests"
        elif prediction["execution_status"] != "completed":
            key = "execution_errors"
        else:
            actual = prediction.get("interpretation") or {}
            fields = ("metric_column", "group_column", "left", "right", "segment_column", "needs_confirmation")
            correct = all(actual.get(field) == gold[field] for field in fields)
            correct = correct and (prediction.get("schema_mapping") or {}).get("aggregation") == "mean"
            key = "correct_automatic_mappings" if correct else "incorrect_automatic_mappings"
        result[key].append(row["case_id"])
    return {"counts": {key: len(value) for key, value in result.items()}, "cases": result,
            "definition": "Automatic mapping requires exact metric, time/buckets, segment/confirmation and mean aggregation. Claim type/tool selection are scored separately. Correct confirmation means a mapping_required response on a gold-ambiguous case; it does not imply all proposed fields are correct."}


def write_report(root="benchmark/results/schema_mapper_v1"):
    root = Path(root)
    verify_frozen(held_out_cases())
    before = json.loads((root.parent / "extension_v1/semantic/summary.json").read_text(encoding="utf-8"))
    old_rows = json.loads((root.parent / "extension_v1/semantic/results.json").read_text(encoding="utf-8"))
    old_gold = {row["case_id"]: row["expected"] for row in old_rows}
    gold_fields = ("expected_status", "expected_error_type", "expected_driver", "should_abstain", "is_clean_control", "expected_interpretation")
    gold_unchanged = all(all(case.metadata[key] == old_gold[case.metadata["case_id"]][key] for key in gold_fields) for case in semantic_cases())
    if not gold_unchanged:
        raise ValueError("Old semantic gold labels changed.")
    summaries = {role: json.loads((root / role / "summary.json").read_text(encoding="utf-8")) for role in ("development", "held_out")}
    rows = {role: json.loads((root / role / "results.json").read_text(encoding="utf-8")) for role in summaries}
    result = {"old_cases_are_development_only": True, "old_gold_labels_unchanged": gold_unchanged,
              "frozen_held_out_verified": True,
              "before_full": before["variants"]["full"]["interpretation"],
              "development_after_full": summaries["development"]["variants"]["full"]["interpretation"],
              "held_out_full": summaries["held_out"]["variants"]["full"]["interpretation"],
              "mapping_outcomes": {role: mapping_outcomes(value) for role, value in rows.items()}}
    lines = ["# Schema Mapper evaluation", "", "Old seven cases: development only. Gold labels unchanged. Frozen held-out inputs and source hashes verified. No post-score prompt/rule changes.", "",
             "## Development before vs after (not held-out evidence)", "", "| Metric | Before | After |", "|---|---:|---:|"]
    for key, (n, d) in result["before_full"]["counts"].items():
        a, b = result["development_after_full"]["counts"][key]
        lines.append(f"| {key} | {n}/{d} | {a}/{b} |")
    lines.extend(["", "## New seven-case held-out results", "", "| Variant | Type | Metric | Time/buckets | Segment/confirmation | Tools | End-to-end |", "|---|---:|---:|---:|---:|---:|---:|"])
    for variant, summary in summaries["held_out"]["variants"].items():
        lines.append(f"| {variant} | " + " | ".join(f"{n}/{d}" for n, d in summary["interpretation"]["counts"].values()) + " |")
    lines.extend(["", "## Full-system mapping outcomes", "", result["mapping_outcomes"]["held_out"]["definition"], ""])
    for role, outcome in result["mapping_outcomes"].items():
        for category, ids in outcome["cases"].items():
            lines.append(f"- {role}/{category}: {len(ids)} ({', '.join(ids) or 'none'}).")
    lines.extend(["", "## Remaining full-system failures and unresolved cases", ""])
    failures = []
    for role, split_rows in rows.items():
        for row in split_rows:
            if row["variant"] != "full":
                continue
            gold = row["expected"]["expected_interpretation"]
            actual = row["prediction"].get("interpretation") or {}
            mismatches = [key for key in gold if (set(actual.get(key) or []) != set(gold[key]) if key == "tool_selection" else actual.get(key) != gold[key])]
            if mismatches or not row["correct"]:
                failure = {"role": role, "case_id": row["case_id"], "execution": row["prediction"]["execution_status"],
                           "expected_status": row["expected"]["expected_status"], "predicted_status": row["prediction"]["predicted_status"], "mismatches": mismatches}
                failures.append(failure)
                lines.append("- " + json.dumps(failure))
    result["failures"] = failures
    lines.extend(["", "## Limitations", "", "Seven held-out cases are a small controlled sample. Mapping-required cases remain unresolved end-to-end, while appropriate human routing is counted separately. Extraction errors cannot be repaired by the mapper. These cases share a mean/greater analytical scope. No analytical thresholds were changed. Mapper/verification explanation token usage is partial. Candidate/sample disclosure is minimized but not a general automatic privacy classifier."])
    (root / "comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(write_report(), indent=2))
