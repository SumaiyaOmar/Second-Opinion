"""Frozen interpretation evaluation. No gold mappings are supplied to predictors."""

from dataclasses import dataclass
import json
import re
import time

import numpy as np
import pandas as pd

from benchmark.cases import AnalysisInput, BenchmarkCase
from benchmark.variants import _call, predict, STATUS, ERRORS, DRIVERS


@dataclass
class SemanticInput(AnalysisInput):
    descriptions: dict


TOOLS = ["audit", "investigation", "critic", "confirmation", "abstain"]


def semantic_cases():
    texts = [
        "Conversion improved in March compared with February.",
        "The share of visits ending in a purchase rose in March compared with February.",
        "Performance improved in March compared with February.",
        "Conversion rose from 10 to 20 in March compared with February, and the campaign caused this improvement.",
        "Conversion improved in March compared with February across customer groups.",
        "March brought a higher conversion yield than February, without any assertion about why.",
        "Overall conversion rose in March compared with February. Check whether customer mix hides weaker performance within each cohort.",
    ]
    cases = []
    for index, text in enumerate(texts):
        rng = np.random.default_rng(12101 + index)
        if index == 6:
            rows = [{"wave": p, "grp": g, "conv_pct": value}
                    for p, g, n, value in (("2026-02", "high", 2, 90), ("2026-02", "low", 18, 30),
                                          ("2026-03", "high", 18, 80), ("2026-03", "low", 2, 20)) for _ in range(n)]
        else:
            rows = [{"wave": p, "grp": g, "conv_pct": value}
                    for p, value in (("2026-01", 0), ("2026-02", 10), ("2026-03", 20), ("2026-04", 30))
                    for g in ("A", "B") for _ in range(20)]
        data = pd.DataFrame(rows).iloc[rng.permutation(len(rows))].reset_index(drop=True)
        descriptions = {"conv_pct": "Conversion percentage: share of visits ending in a purchase; one equally weighted observation per row.",
                        "wave": "Calendar month of observation (ISO YYYY-MM).", "grp": "Customer cohort."}
        if index == 2:
            data["retention_pct"] = data.conv_pct
            descriptions["retention_pct"] = "Customer retention percentage, another plausible measure of performance."
        if index == 4:
            data["region"] = ["North", "South"] * (len(data) // 2)
            descriptions["grp"] = "Customer acquisition channel."
            descriptions["region"] = "Customer geographic area."
        ambiguous = index in {2, 4}
        causal = index == 3
        expected_interpretation = {
            "claim_type": "causal" if causal else "comparison",
            "metric_column": None if index == 2 else "conv_pct", "group_column": "wave",
            "left": "2026-03", "right": "2026-02",
            "segment_column": "grp" if index == 6 else None,
            "needs_confirmation": ambiguous,
            "tool_selection": ["confirmation"] if ambiguous else (["abstain"] if causal else (
                ["audit", "investigation", "critic"] if index == 6 else ["audit", "critic"])),
        }
        metadata = {"case_id": f"semantic-{index + 1:03d}", "split": "semantic_development", "evaluation_role": "development",
                    "case_type": ["column_alias", "business_paraphrase", "ambiguous_metric", "mixed_numeric_causal", "ambiguous_segment", "unusual_clean", "semantic_simpson"][index],
                    "expected_status": "Inconclusive" if ambiguous or causal else ("Partially supported" if index == 6 else "Supported"),
                    "expected_error_type": "causal" if causal else ("insufficient" if ambiguous else ("simpson" if index == 6 else None)),
                    "expected_driver": "mix_effect" if index == 6 else None, "should_abstain": ambiguous or causal,
                    "is_clean_control": index in {0, 1, 5}, "generation_seed": 12101 + index,
                    "expected_interpretation": expected_interpretation,
                    "provenance": "Frozen semantic evaluation; labels fixed before runs; descriptors are schema documentation, not mappings."}
        cases.append(BenchmarkCase(metadata, SemanticInput(data, text, {}, None, descriptions)))
    return cases


def rules_interpret(inputs):
    """Generic aliases and exact month matching; unresolved meanings ask for mapping."""
    text = inputs.claim.casefold()
    causal = bool(re.search(r"\b(caused|causes)\b", text))
    metric_candidates = [column for column in inputs.data if column.casefold() in text]
    if not metric_candidates and "conversion" in text:
        metric_candidates = [column for column in inputs.data if "conversion" in inputs.descriptions.get(column, "").casefold()]
    metric = metric_candidates[0] if len(metric_candidates) == 1 else None
    time_columns = [c for c in inputs.data if any(word in inputs.descriptions.get(c, "").casefold() for word in ("calendar", "month", "date"))]
    group = time_columns[0] if len(time_columns) == 1 else None
    mentions = re.findall(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text)
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    buckets = []
    for month in mentions:
        matches = [] if group is None else [str(v) for v in inputs.data[group].unique() if str(v).endswith(f"-{months.index(month) + 1:02d}")]
        if len(matches) == 1 and matches[0] not in buckets:
            buckets.append(matches[0])
    left, right = (buckets[0], buckets[1]) if len(buckets) == 2 else (None, None)
    needs_segment = any(word in text for word in ("cohort", "customer groups", "customer mix", "segment"))
    segments = [c for c in inputs.data if c not in {metric, group} and not pd.api.types.is_numeric_dtype(inputs.data[c])]
    segment = segments[0] if needs_segment and len(segments) == 1 else None
    confirmation = metric is None or group is None or left is None or (needs_segment and segment is None)
    tools = ["confirmation"] if confirmation else (["abstain"] if causal else ["audit", "critic"] + (["investigation"] if segment else []))
    return dict(claim_type="causal" if causal else "comparison", metric_column=metric,
                group_column=group, left=left, right=right, segment_column=segment,
                needs_confirmation=confirmation, tool_selection=tools)


def predict_semantic(inputs, variant, live=False):
    start = time.perf_counter()
    usage = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "coverage": "complete"}
    result = dict(predicted_status=None, detected_error_type=None, predicted_driver=None, abstained=None,
                  execution_status="not_run", failure=None, estimated_api_cost=None)
    try:
        if variant != "rules_only" and not live:
            result["failure"] = "Live API disabled."
            return result
        if variant == "rules_only":
            interpretation = rules_interpret(inputs)
        else:
            columns = list(inputs.data.columns)
            properties = {"claim_type": {"type": "string", "enum": ["number", "comparison", "causal", "forecast", "recommendation", "other"]},
                          **{key: {"type": ["string", "null"], "enum": [None, *columns]} for key in ("metric_column", "group_column", "segment_column")},
                          "left": {"type": ["string", "null"]}, "right": {"type": ["string", "null"]},
                          "needs_confirmation": {"type": "boolean"},
                          "tool_selection": {"type": "array", "items": {"type": "string", "enum": TOOLS}}}
            if variant == "plain":
                properties.update(status={"type": "string", "enum": STATUS}, error_type={"type": "string", "enum": ERRORS}, driver={"type": "string", "enum": DRIVERS})
            payload = {"claim": inputs.claim, "schema": inputs.descriptions,
                       "bucket_values": {c: inputs.data[c].unique().tolist() for c in columns if not pd.api.types.is_numeric_dtype(inputs.data[c])},
                       "records": inputs.data.to_dict(orient="records") if variant == "plain" else inputs.data.head(5).to_dict(orient="records")}
            interpretation = _call([
                {"role": "system", "content": "Interpret the claim and schema, not gold labels. Distinguish a causal assertion from a negated causal disclaimer. Map metric, time buckets (left=subject, right=baseline), and segment only if requested. Ask confirmation when a metric or segment meaning is ambiguous; do not guess. Recommend required tools: audit+critic for resolved comparisons, add investigation for requested segments/mix; confirmation alone for ambiguous mapping; abstain alone for unsupported causal interpretation. Do not return calculated numbers. Plain-model evaluation additionally supplies status/error/driver with no tool calls. Return JSON."},
                {"role": "user", "content": json.dumps(payload)}],
                {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}, "semantic_interpretation", usage)
        result["interpretation"] = interpretation
        if interpretation["needs_confirmation"] or not interpretation.get("metric_column") or not interpretation.get("group_column"):
            result.update(execution_status="mapping_required", failure="Manual schema/bucket confirmation required.")
        elif variant == "plain":
            if interpretation.get("status") not in STATUS or interpretation.get("error_type") not in ERRORS or interpretation.get("driver") not in DRIVERS:
                raise ValueError("Invalid plain prediction.")
            result.update(execution_status="completed", predicted_status=interpretation["status"],
                          detected_error_type=None if interpretation["error_type"] == "none" else interpretation["error_type"],
                          predicted_driver=None if interpretation["driver"] == "none" else interpretation["driver"], abstained=interpretation["status"] == "Inconclusive")
        else:
            for key in ("metric_column", "group_column", "segment_column"):
                if interpretation.get(key) is not None and interpretation[key] not in inputs.data:
                    raise ValueError("Invalid column mapping.")
            mapping = dict(confirmed=True, calculation_type="two_periods", metric=interpretation["metric_column"],
                           aggregation="mean", operator="greater", group_column=interpretation["group_column"],
                           left=interpretation["left"], right=interpretation["right"])
            extracted = dict(original_claim=inputs.claim, claim_type=interpretation["claim_type"], metric=mapping["metric"],
                             entities_or_segments=[], time_reference=None, direction="increase", needs_calculation=True, notes="")
            analytical = predict(AnalysisInput(inputs.data, inputs.claim, mapping, interpretation.get("segment_column")),
                                 variant, live=live, extracted_claim=extracted)
            result.update(analytical)
            for key in ("model_calls", "prompt_tokens", "completion_tokens", "total_tokens"):
                usage[key] += analytical["model_usage"][key]
            usage["coverage"] = analytical["model_usage"]["coverage"]
    except Exception as exc:
        result.update(execution_status="error", failure=type(exc).__name__, predicted_status=None, abstained=None)
    finally:
        result["model_usage"] = usage
        result["latency_seconds"] = time.perf_counter() - start
    return result


def interpretation_metrics(rows):
    keys = {"claim_type_extraction_accuracy": ("claim_type",), "metric_column_mapping_accuracy": ("metric_column",),
            "time_bucket_mapping_accuracy": ("group_column", "left", "right"),
            "segment_column_mapping_accuracy": ("segment_column", "needs_confirmation"),
            "correct_tool_selection": ("tool_selection",)}
    counts = {}
    attempted = [r for r in rows if r["prediction"]["execution_status"] != "not_run"]
    for metric, fields in keys.items():
        numerator = 0
        for row in attempted:
            gold = row["expected"]["expected_interpretation"]
            actual = row["prediction"].get("interpretation") or {}
            if actual and all(field in actual for field in fields) and all((set(actual.get(field) or []) == set(gold[field]) if field == "tool_selection" else actual.get(field) == gold[field]) for field in fields):
                numerator += 1
        counts[metric] = [numerator, len(attempted)]
    counts["end_to_end_final_status_accuracy"] = [sum(r["correct"] for r in attempted), len(attempted)]
    return {"counts": counts, "metrics": {key: n / d if d else None for key, (n, d) in counts.items()},
            "mapping_required_cases": [r["case_id"] for r in attempted if r["prediction"]["execution_status"] == "mapping_required"]}
