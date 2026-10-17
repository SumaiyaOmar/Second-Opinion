"""Four isolated predictors. None receives case IDs, seeds, types or gold labels."""

import json
import time

from core.auditor import audit_claim
from core.claims import CLAIM_SCHEMA, SYSTEM_PROMPT, validate_claim
from core.critic import run_critic
from core.investigator import investigate_segments
from core.nebius_client import NEBIUS_MODEL, get_nebius_client
from core.verdict import generate_verdict


VARIANTS = ("plain", "rules_only", "no_critic", "full")
ERRORS = ["simpson", "causal", "outlier", "window", "insufficient", "none"]
DRIVERS = ["mix_effect", "within_effect", "volume_effect", "outlier_sensitivity", "window_sensitivity", "none"]
STATUS = ["Supported", "Partially supported", "Unsupported", "Inconclusive"]


def _call(messages, schema, name, usage):
    usage["model_calls"] += 1
    with get_nebius_client() as client:
        response = client.chat.completions.create(model=NEBIUS_MODEL, temperature=0,
            messages=messages, response_format={"type": "json_schema", "json_schema": {
                "name": name, "strict": True, "schema": schema}})
    if response.usage:
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[field] += getattr(response.usage, field, 0) or 0
    return json.loads(response.choices[0].message.content)


def _rules_extract(inputs):
    """Frozen minimal baseline parser, using the same confirmed mapping as tools variants."""
    return {"original_claim": inputs.claim,
            "claim_type": "causal" if "caused" in inputs.claim.casefold() else "comparison",
            "metric": inputs.mapping["metric"], "entities_or_segments": [],
            "time_reference": None, "direction": "increase", "needs_calculation": True, "notes": ""}


def _interpret(audit, inv, critic, claim):
    """Fixed benchmark adapter for categorical error/driver output; no gold access."""
    failed = {c["name"] for c in (critic or {}).get("checks_run", []) if c["status"] == "failed"}
    if claim["claim_type"] == "causal":
        return "causal", None
    if inv and inv.get("finding") == "direction_reversal":
        return "simpson", (inv.get("strongest_supported_driver") or {}).get("component")
    if "outlier_removal" in failed or "mean_vs_median" in failed:
        return "outlier", "outlier_sensitivity"
    if "alternative_window" in failed:
        return "window", "window_sensitivity"
    if audit["status"] == "Inconclusive" or (critic and critic["checks_inconclusive"] and not critic["checks_passed"] and not critic["checks_failed"]):
        return "insufficient", None
    if inv and inv.get("finding") == "mix_shift":
        return "simpson", (inv.get("strongest_supported_driver") or {}).get("component")
    return None, None


def predict(inputs, variant, live=False, extracted_claim=None):
    if variant not in VARIANTS:
        raise ValueError("Unknown variant.")
    start = time.perf_counter()
    usage = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
             "coverage": "complete"}
    result = {"predicted_status": None, "detected_error_type": None, "predicted_driver": None,
              "abstained": None, "execution_status": "completed", "failure": None}
    try:
        if variant != "rules_only" and not live:
            result.update(execution_status="not_run", failure="Live API disabled; variant not replaced by an offline approximation.")
        elif variant == "plain":
            schema = {"type": "object", "properties": {
                "status": {"type": "string", "enum": STATUS},
                "error_type": {"type": "string", "enum": ERRORS},
                "driver": {"type": "string", "enum": DRIVERS}},
                "required": ["status", "error_type", "driver"], "additionalProperties": False}
            summary = {"claim": inputs.claim, "confirmed_mapping": inputs.mapping,
                       "segment_column": inputs.segment_column,
                       "profile": json.loads(inputs.data.describe(include="all").to_json()),
                       "records": inputs.data.to_dict(orient="records")}
            output = _call([
                {"role": "system", "content": "Evaluate the claim using only the supplied dataset and summary. No tools are available. Observational data does not establish causation. Return status, error_type and strongest driver, or none; abstain with Inconclusive if needed."},
                {"role": "user", "content": json.dumps(summary)}], schema, "plain_evaluation", usage)
            if output.get("status") not in STATUS or output.get("error_type") not in ERRORS or output.get("driver") not in DRIVERS:
                raise ValueError("Invalid plain-model prediction.")
            result.update(predicted_status=output["status"], detected_error_type=None if output["error_type"] == "none" else output["error_type"],
                          predicted_driver=None if output["driver"] == "none" else output["driver"])
        else:
            claim = extracted_claim if extracted_claim is not None else (_rules_extract(inputs) if variant == "rules_only" else validate_claim(_call([
                {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": inputs.claim}],
                CLAIM_SCHEMA, "claim_extraction", usage), inputs.claim))
            audit = audit_claim(inputs.data, claim, inputs.mapping)
            inv = None
            if inputs.segment_column and audit["status"] != "Inconclusive" and claim["claim_type"] == "comparison":
                inv = investigate_segments(inputs.data, claim, audit, inputs.mapping, inputs.segment_column, True)
            critic = None
            if variant in {"rules_only", "full"}:
                critic = run_critic(inputs.data, claim, audit, inputs.mapping,
                                    inputs.segment_column, inputs.segment_column is not None, inv)
                verdict = generate_verdict(claim, audit, inv, critic, use_model=variant == "full")
                status = verdict["final_status"]
                result["corrected_conclusion"] = verdict["corrected_conclusion"]
                if variant == "full":
                    # Core verdict intentionally hides provider usage; never invent token counts.
                    usage["model_calls"] += 1
                    usage["coverage"] = "partial: verdict explanation tokens unavailable"
                    result["explanation_source"] = verdict["computational_receipts"]["explanation_source"]
            else:
                # Explicit ablation policy: do not invoke final verdict with a missing Critic.
                status = audit["status"]
                if status == "Supported" and inv:
                    status = "Inconclusive" if inv["finding"] == "inconclusive" else (
                        "Partially supported" if inv["finding"] in {"direction_reversal", "mix_shift"} else "Supported")
            error, driver = _interpret(audit, inv, critic, claim)
            result.update(predicted_status=status, detected_error_type=error, predicted_driver=driver)
            result["analytical_evidence"] = {"audit_status": audit["status"],
                "aggregate_values": audit["computed_values"], "difference": audit["difference"],
                "investigation_finding": (inv or {}).get("finding"),
                "segment_results": (inv or {}).get("segment_results"),
                "mix_shift_evidence": (inv or {}).get("mix_shift_evidence")}
        if result["execution_status"] == "completed":
            result["abstained"] = result["predicted_status"] == "Inconclusive"
    except Exception as exc:
        # An API/runtime failure is an evaluation failure, never a correct abstention.
        result.update(execution_status="error", failure=type(exc).__name__, predicted_status=None, abstained=None)
    result["latency_seconds"] = time.perf_counter() - start
    result["model_usage"] = usage
    result["estimated_api_cost"] = None
    return result
