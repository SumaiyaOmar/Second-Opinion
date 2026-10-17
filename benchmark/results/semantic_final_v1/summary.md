# Benchmark: semantic_final_held_out

Cases: 12. Frozen seeds: (34101, 34102, 34103, 34104, 34105, 34106, 34107, 34108, 34109, 34110, 34111, 34112).

| Variant | Completed | Errors | Not run | Detection | False alarm | Status accuracy | Abstention | Driver rank-1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| plain | 7 | 0 | 0 | 0.000 | 0.167 | 0.714 | not measured | 1.000 |
| rules_only | 0 | 0 | 0 | not measured | not measured | not measured | not measured | not measured |
| no_critic | 9 | 1 | 0 | 0.500 | 0.000 | 0.900 | 1.000 | 0.000 |
| full | 7 | 1 | 0 | 0.000 | 0.286 | 0.625 | not measured | 0.000 |

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
| plain | 9/12 | 11/12 | 1/12 | 4/12 | 6/12 | 5/12 | semantic-final-002, semantic-final-003, semantic-final-004, semantic-final-005, semantic-final-006 |
| rules_only | 12/12 | 1/12 | 12/12 | 2/12 | 2/12 | 0/12 | semantic-final-001, semantic-final-002, semantic-final-003, semantic-final-004, semantic-final-005, semantic-final-006, semantic-final-007, semantic-final-008, semantic-final-009, semantic-final-010, semantic-final-011, semantic-final-012 |
| no_critic | 11/12 | 11/12 | 11/12 | 11/12 | 11/12 | 9/12 | semantic-final-005, semantic-final-006 |
| full | 11/12 | 11/12 | 11/12 | 9/12 | 9/12 | 5/12 | semantic-final-004, semantic-final-005, semantic-final-006, semantic-final-008 |

## Failures (status, driver, or error classification)

- plain: [{"case_id": "semantic-final-007", "expected_status": "Partially supported", "predicted_status": "Inconclusive", "expected_driver": "mix_effect", "predicted_driver": "mix_effect", "execution_status": "completed", "error_type_correct": false}, {"case_id": "semantic-final-012", "expected_status": "Supported", "predicted_status": "Partially supported", "expected_driver": null, "predicted_driver": "mix_effect", "execution_status": "completed", "error_type_correct": true}]
- rules_only: []
- no_critic: [{"case_id": "semantic-final-007", "expected_status": "Partially supported", "predicted_status": null, "expected_driver": "mix_effect", "predicted_driver": null, "execution_status": "error", "error_type_correct": false}]
- full: [{"case_id": "semantic-final-003", "expected_status": "Supported", "predicted_status": "Inconclusive", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": true}, {"case_id": "semantic-final-007", "expected_status": "Partially supported", "predicted_status": null, "expected_driver": "mix_effect", "predicted_driver": null, "execution_status": "error", "error_type_correct": false}, {"case_id": "semantic-final-011", "expected_status": "Supported", "predicted_status": "Inconclusive", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": true}]

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
