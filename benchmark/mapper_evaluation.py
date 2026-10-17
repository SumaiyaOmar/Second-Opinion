"""Dedicated mapper ablation adapter; no gold labels passed to the pipeline."""

import time

from benchmark.cases import AnalysisInput
from benchmark.semantic import predict_semantic, rules_interpret
from benchmark.variants import predict, _call
from core.claims import SYSTEM_PROMPT, CLAIM_SCHEMA, validate_claim
from core.schema_mapper import map_schema, schema_profile, validate_mapping, manual_mapping


def predict_with_mapper(inputs, variant, live=False):
    if variant == "plain":
        return predict_semantic(inputs, variant, live)
    start = time.perf_counter()
    usage = dict(model_calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0, coverage="complete")
    result = dict(execution_status="not_run", predicted_status=None, detected_error_type=None,
                  predicted_driver=None, abstained=None, failure=None, estimated_api_cost=None)
    try:
        if variant != "rules_only" and not live:
            return result
        if variant == "rules_only":
            old = rules_interpret(inputs)
            extracted = dict(original_claim=inputs.claim, claim_type=old["claim_type"], metric=old["metric_column"],
                             entities_or_segments=[], time_reference=None, direction="increase", needs_calculation=True, notes="")
            mapping = dict(metric_column=old["metric_column"], time_column=old["group_column"],
                comparison_bucket=old["left"], baseline_bucket=old["right"], segment_column=old["segment_column"],
                aggregation="mean", needs_confirmation=old["needs_confirmation"], candidate_alternatives=[],
                ambiguities=[], reasoning_summary="Frozen rules baseline using aliases and month labels.")
            try:
                mapping = validate_mapping(mapping, inputs.data, inputs.claim, extracted,
                                           schema_profile(inputs.data, list(inputs.data.columns), inputs.descriptions), recover=True)
            except ValueError:
                mapping = manual_mapping("Rules proposal requires manual mapping.")
        else:
            extracted = validate_claim(_call([
                {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": inputs.claim}],
                CLAIM_SCHEMA, "claim_extraction", usage), inputs.claim)
            usage["model_calls"] += 1
            usage["coverage"] = "partial: core mapper and verdict token usage unavailable"
            mapping = map_schema(inputs.claim, extracted, inputs.data, list(inputs.data.columns), inputs.descriptions)
        tools = ["confirmation"] if mapping["needs_confirmation"] else (["abstain"] if extracted["claim_type"] == "causal" else ["audit", "critic"] + (["investigation"] if mapping["segment_column"] else []))
        interpretation = dict(claim_type=extracted["claim_type"], metric_column=mapping["metric_column"],
            group_column=mapping["time_column"], left=mapping["comparison_bucket"], right=mapping["baseline_bucket"],
            segment_column=mapping["segment_column"], needs_confirmation=mapping["needs_confirmation"], tool_selection=tools)
        result.update(interpretation=interpretation, schema_mapping=mapping)
        if mapping["needs_confirmation"]:
            result.update(execution_status="mapping_required", failure="Validated mapping requires user confirmation.")
        else:
            confirmed = dict(confirmed=True, calculation_type="two_periods", metric=mapping["metric_column"],
                aggregation=mapping["aggregation"], operator="greater", group_column=mapping["time_column"],
                left=mapping["comparison_bucket"], right=mapping["baseline_bucket"])
            analytical = predict(AnalysisInput(inputs.data, inputs.claim, confirmed, mapping["segment_column"]),
                                 variant, live, extracted_claim=extracted)
            result.update(analytical)
            for key in ("model_calls", "prompt_tokens", "completion_tokens", "total_tokens"):
                usage[key] += analytical["model_usage"][key]
    except Exception as exc:
        result.update(execution_status="error", failure=type(exc).__name__)
    finally:
        result["latency_seconds"] = time.perf_counter() - start
        result["model_usage"] = usage
    return result
