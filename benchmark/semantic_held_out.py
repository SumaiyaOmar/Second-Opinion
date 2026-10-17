"""Former mapper-v1 held-out cases; development-only following reliability work."""

import numpy as np
import pandas as pd

from benchmark.cases import BenchmarkCase
from benchmark.semantic import SemanticInput


def held_out_cases():
    specifications = [
        ("order_yield", "cycle_key", "traffic_family", "Average checkout completion was higher in June than May.", False, False, False),
        ("renewal_rate", "snapshot", "account_tier", "The fraction of accounts renewing was higher in September than August.", False, False, False),
        ("quality_index", "measurement_month", "branch_code", "Business performance improved in November compared with October.", True, False, False),
        ("basket_rate", "report_month", "shop_cluster", "Average purchase completion rose from 15 to 27 in June compared with May, and the redesign caused that increase.", False, True, False),
        ("enrollment_pct", "survey_cycle", "recruitment_path", "Average enrollment increased in September versus August across segments.", False, False, True),
        ("uptake_rate", "observed_month", "subscriber_class", "The latest observed month had a higher average uptake rate than the previous observed month; no causal explanation is asserted.", False, False, False),
        ("fulfillment_pct", "release_month", "facility_band", "Average fulfillment rose in November versus October. Check whether a shift in facility mix hides lower results within each facility band.", False, False, False),
    ]
    cases = []
    for index, (metric, time, segment, text, ambiguous_metric, causal, ambiguous_segment) in enumerate(specifications):
        rng = np.random.default_rng(23111 + index)
        months = [("2027-04", "2027-05", "2027-06", "2027-07"), ("2027-07", "2027-08", "2027-09", "2027-10"),
                  ("2027-09", "2027-10", "2027-11", "2027-12")][index % 3]
        if index == 5:
            months = months[:3]  # Latest = November, previous = October.
        before, after = months[1:3]
        if index == 6:
            months = ("2027-09", "2027-10", "2027-11", "2027-12")
            before, after = months[1:3]
            rows = [{time: p, segment: group, metric: value}
                    for p, group, n, value in ((before, "priority", 3, 85), (before, "standard", 27, 35),
                                               (after, "priority", 27, 75), (after, "standard", 3, 25)) for _ in range(n)]
        else:
            rows = [{time: p, segment: group, metric: value}
                    for p, value in zip(months, (3, 15, 27, 39)) for group in ("I", "II") for _ in range(24)]
        data = pd.DataFrame(rows).iloc[rng.permutation(len(rows))].reset_index(drop=True)
        concept = ["checkout completion", "accounts renewing", "quality", "purchase completion", "enrollment", "uptake", "fulfillment"][index]
        descriptions = {metric: f"Average {concept} rate per equally weighted observation.", time: "Calendar month of observation in ISO YYYY-MM format.",
                        segment: "Facility band." if index == 6 else "Customer category."}
        if ambiguous_metric:
            data["margin_index"] = data[metric]
            descriptions["margin_index"] = "Profit margin index; another business performance measure."
        if ambiguous_segment:
            data["territory_code"] = ["East", "West"] * (len(data) // 2)
            descriptions["territory_code"] = "Geographic segment."
        ambiguous = ambiguous_metric or ambiguous_segment
        gold = dict(claim_type="causal" if causal else "comparison", metric_column=None if ambiguous_metric else metric,
                    group_column=time, left=after, right=before, segment_column=segment if index == 6 else None,
                    needs_confirmation=ambiguous, tool_selection=["confirmation"] if ambiguous else (["abstain"] if causal else (
                        ["audit", "investigation", "critic"] if index == 6 else ["audit", "critic"])))
        cases.append(BenchmarkCase(dict(case_id=f"semantic-held-out-{index + 1:03d}", split="semantic_mapper_development", evaluation_role="development",
            case_type=["renamed_metric_time", "paraphrase", "ambiguous_metric", "mixed_numeric_causal", "ambiguous_segments", "relative_window_control", "renamed_mix_reversal"][index],
            expected_status="Inconclusive" if causal or ambiguous else ("Partially supported" if index == 6 else "Supported"),
            expected_error_type="causal" if causal else ("insufficient" if ambiguous else ("simpson" if index == 6 else None)),
            expected_driver="mix_effect" if index == 6 else None, should_abstain=causal or ambiguous,
            is_clean_control=index in {0, 1, 5}, generation_seed=23111 + index, expected_interpretation=gold,
            provenance="Former mapper-v1 held-out set; now development-only. Original case IDs, data, seeds and gold labels retained."),
            SemanticInput(data, text, {}, None, descriptions)))
    return cases
