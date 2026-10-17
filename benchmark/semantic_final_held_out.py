"""Final semantic held-out v1: generation/freezing only until explicitly scored."""

import numpy as np
import pandas as pd

from benchmark.cases import BenchmarkCase
from benchmark.semantic import SemanticInput


SPECS = [
    ("appointment_attendance", "slot_month", "clinic_kind", "renamed_control", "Average appointment attendance was higher in August than July."),
    ("timely_dispatch", "ledger_cycle", "carrier_band", "business_paraphrase", "A larger average share of shipments left on time in August versus July."),
    ("return_visit_rate", "visit_period", "practice_zone", "relative_window_control", "The most recent observed month had a greater average return-visit rate than the prior observed month."),
    ("first_pass_pct", "batch_month", "line_family", "mixed_numeric_causal", "Average first-pass yield rose from 20 to 32 in August versus July, and the new process caused that increase."),
    ("engagement_index", "panel_period", "subscriber_band", "ambiguous_metric", "Average performance was stronger in August than July."),
    ("member_signup_share", "reporting_cycle", "audience_band", "ambiguous_segment", "Average membership signup was higher in August versus July across categories."),
    ("room_readiness", "release_cycle", "property_band", "mix_reversal", "Average room readiness rose in August versus July. Test whether property mix conceals lower readiness within each property band."),
    ("invoice_clearance", "close_period", "client_band", "explicit_segment", "Compare average invoice clearance within each client cohort: August exceeded July."),
    ("supply_fill_pct", "stock_period", "supplier_band", "no_segment_control", "Only compare overall average supply fill in August versus July. No segment breakdown is requested."),
    ("service_score", "calendar_window", "desk_band", "overall_control", "Overall average service quality was higher in August than July; do not segment this comparison."),
    ("quality_compliance", "review_month", "plant_band", "explicit_category", "Report average compliance for each plant category in August versus July."),
    ("practice_completion", "session_month", "delivery_mode", "no_segmentation_control", "August showed more average practice completion than July, without segmentation."),
]


def final_held_out_cases():
    cases = []
    periods = ("2031-06", "2031-07", "2031-08", "2031-09")
    for index, (metric, time, segment, kind, text) in enumerate(SPECS):
        rng = np.random.default_rng(34101 + index)
        base = 17 + index
        if kind == "mix_reversal":
            rows = [{time: period, segment: group, metric: value}
                    for period, group, n, value in ((periods[1], "priority", 4, 91), (periods[1], "standard", 36, 41),
                                                  (periods[2], "priority", 36, 81), (periods[2], "standard", 4, 31)) for _ in range(n)]
        else:
            rows = [{time: period, segment: group, metric: value}
                    for period, value in zip(periods, (base - 12, base, base + 12, base + 24))
                    for group in ("direct", "assisted") for _ in range(24)]
        data = pd.DataFrame(rows).iloc[rng.permutation(len(rows))].reset_index(drop=True)
        descriptions = {metric: "Average " + metric.replace("_", " ") + " per equally weighted observation.",
                        time: "Calendar month of observation, ISO YYYY-MM.", segment: segment.replace("_", " ") + "; categorical grouping."}
        if kind == "ambiguous_metric":
            data["contribution_index"] = data[metric] + 2
            descriptions["contribution_index"] = "Another business performance measure: average contribution index."
        if kind in {"ambiguous_segment", "no_segment_control"}:
            data["service_territory"] = ["Coastal", "Inland"] * (len(data) // 2)
            descriptions["service_territory"] = "Geographic category."
        ambiguous = kind in {"ambiguous_metric", "ambiguous_segment"}
        causal = kind == "mixed_numeric_causal"
        needs_segment = kind in {"mix_reversal", "explicit_segment", "explicit_category"}
        baseline, comparison = (periods[2], periods[3]) if kind == "relative_window_control" else (periods[1], periods[2])
        expected_interpretation = dict(claim_type="causal" if causal else "comparison",
            metric_column=None if kind == "ambiguous_metric" else metric, group_column=time,
            left=comparison, right=baseline, segment_column=segment if needs_segment else None,
            needs_confirmation=ambiguous, tool_selection=["confirmation"] if ambiguous else (["abstain"] if causal else (
                ["audit", "investigation", "critic"] if needs_segment else ["audit", "critic"])))
        metadata = dict(case_id=f"semantic-final-{index + 1:03d}", split="semantic_final_held_out", evaluation_role="held_out",
            case_type=kind, expected_status="Inconclusive" if ambiguous or causal else ("Partially supported" if kind == "mix_reversal" else "Supported"),
            expected_error_type="causal" if causal else ("insufficient" if ambiguous else ("simpson" if kind == "mix_reversal" else None)),
            expected_driver="mix_effect" if kind == "mix_reversal" else None,
            should_abstain=ambiguous or causal, is_clean_control=not ambiguous and not causal and kind != "mix_reversal",
            generation_seed=34101 + index, expected_interpretation=expected_interpretation,
            provenance="New final frozen semantic set; not scored during reliability implementation. Gold labels fixed independently of predictions.")
        cases.append(BenchmarkCase(metadata, SemanticInput(data, text, {}, None, descriptions)))
    return cases
