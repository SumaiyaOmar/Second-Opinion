# Benchmark: semantic_development

Cases: 7. Frozen seeds: (12101, 12102, 12103, 12104, 12105, 12106, 12107).

| Variant | Completed | Errors | Not run | Detection | False alarm | Status accuracy | Abstention | Driver rank-1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| plain | 2 | 0 | 0 | 0.000 | 0.000 | 0.500 | not measured | 1.000 |
| rules_only | 4 | 0 | 0 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| no_critic | 4 | 1 | 0 | 0.500 | 0.000 | 0.800 | 1.000 | 0.000 |
| full | 4 | 1 | 0 | 0.500 | 0.000 | 0.800 | 1.000 | 0.000 |

## Metric definitions

- error_detection_rate: Non-control labeled errors with a completed non-Supported prediction and non-null detected error / all attempted labeled errors.
- false_alarm_rate: Clean controls not completed as Supported with no detected error / all attempted clean controls; execution failures count as alarms.
- final_status_accuracy: Exact final-status matches / all attempted cases; execution errors are incorrect.
- correct_abstention_rate: Completed Inconclusive predictions / all attempted should_abstain cases; API failures are not abstentions.
- rank1_driver_accuracy: Exact top driver matches / attempted cases with a non-null expected_driver.
- per_error_class_accuracy: Exact status accuracy within each case_type, including clean controls.

## Interpretation (separate from conditional analytical metrics)

Exact field/set matches; missing/error responses score incorrect. End-to-end denominator includes mapping-required cases (no final verdict). Segment mapping includes correct confirmation behavior. Tool selection is recommended, not necessarily executed.

| Variant | Claim type | Metric column | Time/buckets | Segment/confirmation | Recommended tools | End-to-end status | Mapping required |
|---|---:|---:|---:|---:|---:|---:|---|
| plain | 3/7 | 6/7 | 0/7 | 1/7 | 3/7 | 1/7 | semantic-001, semantic-003, semantic-004, semantic-005, semantic-006 |
| rules_only | 7/7 | 6/7 | 7/7 | 6/7 | 6/7 | 4/7 | semantic-002, semantic-003, semantic-005 |
| no_critic | 6/7 | 6/7 | 6/7 | 6/7 | 6/7 | 4/7 | semantic-003, semantic-005 |
| full | 6/7 | 6/7 | 6/7 | 6/7 | 6/7 | 4/7 | semantic-003, semantic-005 |

## Failures (status, driver, or error classification)

- plain: [{"case_id": "semantic-007", "expected_status": "Partially supported", "predicted_status": "Supported", "expected_driver": "mix_effect", "predicted_driver": "mix_effect", "execution_status": "completed", "error_type_correct": false}]
- rules_only: []
- no_critic: [{"case_id": "semantic-007", "expected_status": "Partially supported", "predicted_status": null, "expected_driver": "mix_effect", "predicted_driver": null, "execution_status": "error", "error_type_correct": false}]
- full: [{"case_id": "semantic-007", "expected_status": "Partially supported", "predicted_status": null, "expected_driver": "mix_effect", "predicted_driver": null, "execution_status": "error", "error_type_correct": false}]

## Limitations

- Development results are debugging results, not independent evidence.
- Held-out seeds are frozen separately; these tiny structurally matched synthetic cases are not broad real-world generalization evidence.
- Each synthetic split has one case per class; rates have very small denominators.
- All variants receive identical confirmed mappings and row data; model variants additionally use model extraction, so rules-only vs full is not a single-factor ablation.
- Plain Nemotron gets a generic profile and all records, no deterministic comparison, investigation, or stress outputs.
- No-Critic uses an explicitly documented audit/investigation-only decision policy, not the full verdict policy with missing inputs.
- Tool-based error/driver labels use a fixed evidence adapter; they are benchmark categories, not new application analysis rules.
- Rules-only uses a deliberately minimal frozen parser; causal language beyond its literal pattern is not covered.
- Live-model results may change despite temperature zero; there is no provider-side seed guarantee.
- Full variant reports only extraction token usage; explanation tokens are unavailable through the existing Verdict interface. Cost is null, not invented.
- Kidney-stone data are locally transcribed observational counts, expanded anonymously; no patient covariates or causal superiority are inferred.
- Semantic inputs contain schema descriptions but no confirmed mappings. mapping_required is excluded from analytical rates and reported separately as unresolved end-to-end coverage.
- Semantic tool-selection accuracy measures recommended tests, not execution; no-Critic still omits Critic. A fixed mean/greater scaffold applies to this small all-increase semantic split.
