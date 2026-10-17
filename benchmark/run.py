"""CLI: python -m benchmark.run --split held_out --variant all --live"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import hashlib
from importlib.metadata import version
from pathlib import Path

from benchmark.cases import generated_cases, load_documented_cases, SEEDS
from benchmark.metrics import DEFINITIONS, score_row, summarize
from benchmark.variants import VARIANTS, predict
from core.critic import RULES
from benchmark.semantic import semantic_cases, predict_semantic, interpretation_metrics
from benchmark.mapper_evaluation import predict_with_mapper
from benchmark.semantic_held_out import held_out_cases
from benchmark.semantic_final_held_out import final_held_out_cases
from benchmark.freeze_final_mapper import verify_final_frozen


LIMITATIONS = [
    "Development results are debugging results, not independent evidence.",
    "Held-out seeds are frozen separately; these tiny structurally matched synthetic cases are not broad real-world generalization evidence.",
    "Each synthetic split has one case per class; rates have very small denominators.",
    "All variants receive identical confirmed mappings and row data; model variants additionally use model extraction, so rules-only vs full is not a single-factor ablation.",
    "Plain Nemotron gets a generic profile and all records, no deterministic comparison, investigation, or stress outputs.",
    "No-Critic uses an explicitly documented audit/investigation-only decision policy, not the full verdict policy with missing inputs.",
    "Tool-based error/driver labels use a fixed evidence adapter; they are benchmark categories, not new application analysis rules.",
    "Rules-only uses a deliberately minimal frozen parser; causal language beyond its literal pattern is not covered.",
    "Live-model results may change despite temperature zero; there is no provider-side seed guarantee.",
    "Full variant reports only extraction token usage; explanation tokens are unavailable through the existing Verdict interface. Cost is null, not invented.",
    "Kidney-stone data are locally transcribed observational counts, expanded anonymously; no patient covariates or causal superiority are inferred.",
    "Semantic inputs contain schema descriptions but no confirmed mappings. mapping_required is excluded from analytical rates and reported separately as unresolved end-to-end coverage.",
    "Semantic tool-selection accuracy measures recommended tests, not execution; no-Critic still omits Critic. A fixed mean/greater scaffold applies to this small all-increase semantic split.",
]


def run_benchmark(split="development", variant="rules_only", output="benchmark/results", live=False,
                  workers=1, manifest=None):
    cases = (load_documented_cases(manifest or Path(__file__).parent / "documented/manifest.json") if split == "real_documented"
             else final_held_out_cases() if split == "semantic_final_held_out"
             else held_out_cases() if split in {"semantic_held_out", "semantic_mapper_development"}
             else semantic_cases() if split in {"semantic", "semantic_development"} else generated_cases(split))
    reported_split = "semantic_development" if split == "semantic" else split
    if split == "semantic_held_out":
        reported_split = "semantic_mapper_development"
    semantic_split = split.startswith("semantic")
    if split == "semantic_final_held_out":
        verify_final_frozen(cases)
    variants = VARIANTS if variant == "all" else (variant,)
    if any(v not in VARIANTS for v in variants):
        raise ValueError("Unknown variant.")
    tasks = [(case, v) for v in variants for case in cases]
    def evaluate(task):
        case, v = task
        # Prediction receives only AnalysisInput; expected labels joined afterward.
        predictor = predict_with_mapper if semantic_split else predict
        return score_row(case.metadata, predictor(case.inputs, v, live=live), v)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(evaluate, tasks))
    summaries = {v: summarize([r for r in rows if r["variant"] == v]) for v in variants}
    if semantic_split:
        for v in variants:
            summaries[v]["interpretation"] = interpretation_metrics([r for r in rows if r["variant"] == v])
    report = {"split": reported_split, "evaluation_role": "development" if reported_split in {"semantic_development", "semantic_mapper_development"} else "held_out" if reported_split == "semantic_final_held_out" else reported_split,
              "case_count": len(cases), "seeds": SEEDS.get(split, tuple(c.metadata["generation_seed"] for c in cases if c.metadata["generation_seed"] is not None)),
              "configuration": {"critic_rules": RULES, "investigator_min_segment_rows": 2,
                  "investigator_material_fraction": 0.10, "verdict_rules_version": "verdict_v1",
                  "versions": {name: version(name) for name in ("numpy", "pandas", "openai")},
                  "source_sha256": {name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                      for name in ("core/claims.py", "core/auditor.py", "core/investigator.py", "core/critic.py", "core/verdict.py", "core/schema_mapper.py", "core/schema_mapping_validation.py", "tools/analytics.py", "benchmark/cases.py", "benchmark/variants.py", "benchmark/semantic.py", "benchmark/mapper_evaluation.py", "benchmark/semantic_held_out.py", "benchmark/semantic_final_held_out.py")}},
              "case_counts_by_type": {kind: sum(c.metadata["case_type"] == kind for c in cases) for kind in sorted({c.metadata["case_type"] for c in cases})},
              "model": "nvidia/Nemotron-3_5-Lightning", "metric_definitions": DEFINITIONS,
              "variants": summaries, "limitations": LIMITATIONS}
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "results.json").write_text(json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    fields = ["case_id", "split", "variant", "case_type", "generation_seed", "expected_status", "expected_error_type", "expected_driver",
              "should_abstain", "is_clean_control", "predicted_status", "detected_error_type", "predicted_driver", "abstained",
              "correct", "error_type_correct", "driver_correct", "execution_status", "failure", "latency_seconds", "model_usage", "estimated_api_cost", "interpretation"]
    with (directory / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {**row["expected"], **row["prediction"], "variant": row["variant"],
                    "correct": row["correct"], "error_type_correct": row["error_type_correct"], "driver_correct": row["driver_correct"]}
            flat["model_usage"] = json.dumps(flat.get("model_usage"))
            flat["interpretation"] = json.dumps(flat.get("interpretation"))
            writer.writerow({key: flat.get(key) for key in fields})
    def display(value):
        return "not measured" if value is None else f"{value:.3f}"
    lines = [f"# Benchmark: {reported_split}", "", f"Cases: {len(cases)}. Frozen seeds: {report['seeds']}.", "",
             "| Variant | Completed | Errors | Not run | Detection | False alarm | Status accuracy | Abstention | Driver rank-1 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v in variants:
        s = summaries[v]
        lines.append(f"| {v} | {s['completed']} | {s['execution_errors']} | {s['not_run']} | " + " | ".join(display(s["metrics"][key]) for key in (
            "error_detection_rate", "false_alarm_rate", "final_status_accuracy", "correct_abstention_rate", "rank1_driver_accuracy")) + " |")
    lines.extend(["", "## Metric definitions", ""] + [f"- {name}: {definition}" for name, definition in DEFINITIONS.items()])
    if semantic_split:
        lines.extend(["", "## Interpretation (separate from conditional analytical metrics)", "",
            "Exact field/set matches; missing/error responses score incorrect. End-to-end denominator includes mapping-required cases (no final verdict). Segment mapping includes correct confirmation behavior. Tool selection is recommended, not necessarily executed.", "",
            "| Variant | Claim type | Metric column | Time/buckets | Segment/confirmation | Recommended tools | End-to-end status | Mapping required |",
            "|---|---:|---:|---:|---:|---:|---:|---|"])
        for v in variants:
            interpretation = summaries[v]["interpretation"]
            lines.append(f"| {v} | " + " | ".join(f"{n}/{d}" for n, d in interpretation["counts"].values()) + " | " + ", ".join(interpretation["mapping_required_cases"]) + " |")
    lines.extend(["", "## Failures (status, driver, or error classification)", ""])
    for v, summary in summaries.items():
        lines.append(f"- {v}: {json.dumps(summary['failures'])}")
    lines.extend(["", "## Limitations", ""] + [f"- {item}" for item in LIMITATIONS])
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held_out", "real_documented", "semantic", "semantic_development", "semantic_held_out", "semantic_mapper_development", "semantic_final_held_out"], default="development")
    parser.add_argument("--variant", choices=[*VARIANTS, "all"], default="rules_only")
    parser.add_argument("--live", action="store_true", help="Enable model calls; otherwise live variants are explicitly not_run.")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", default="benchmark/results")
    parser.add_argument("--manifest")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 4:
        parser.error("workers must be between 1 and 4")
    report = run_benchmark(args.split, args.variant, args.output, args.live, args.workers, args.manifest)
    print(json.dumps({"split": report["split"], "cases": report["case_count"], "variants": report["variants"]}, indent=2))


if __name__ == "__main__":
    main()
