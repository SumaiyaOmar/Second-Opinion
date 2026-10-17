# Benchmark: held_out

Cases: 6. Frozen seeds: (8101, 8102, 8103, 8104, 8105, 8106).

| Variant | Completed | Errors | Not run | Detection | False alarm | Status accuracy | Abstention | Driver rank-1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| plain | 5 | 1 | 0 | 0.200 | 0.000 | 0.333 | 0.500 | 0.333 |
| rules_only | 6 | 0 | 0 | 0.800 | 0.000 | 1.000 | 1.000 | 1.000 |
| no_critic | 6 | 0 | 0 | 0.400 | 0.000 | 0.500 | 0.500 | 0.333 |
| full | 6 | 0 | 0 | 0.800 | 0.000 | 1.000 | 1.000 | 1.000 |

## Metric definitions

- error_detection_rate: Non-control labeled errors with a completed non-Supported prediction and non-null detected error / all attempted labeled errors.
- false_alarm_rate: Clean controls not completed as Supported with no detected error / all attempted clean controls; execution failures count as alarms.
- final_status_accuracy: Exact final-status matches / all attempted cases; execution errors are incorrect.
- correct_abstention_rate: Completed Inconclusive predictions / all attempted should_abstain cases; API failures are not abstentions.
- rank1_driver_accuracy: Exact top driver matches / attempted cases with a non-null expected_driver.
- per_error_class_accuracy: Exact status accuracy within each case_type, including clean controls.

## Failures (status, driver, or error classification)

- plain: [{"case_id": "held_out-001", "expected_status": "Partially supported", "predicted_status": null, "expected_driver": "mix_effect", "predicted_driver": null, "execution_status": "error", "error_type_correct": false}, {"case_id": "held_out-003", "expected_status": "Partially supported", "predicted_status": "Supported", "expected_driver": "outlier_sensitivity", "predicted_driver": "outlier_sensitivity", "execution_status": "completed", "error_type_correct": false}, {"case_id": "held_out-004", "expected_status": "Partially supported", "predicted_status": "Supported", "expected_driver": "window_sensitivity", "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}, {"case_id": "held_out-005", "expected_status": "Inconclusive", "predicted_status": "Supported", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}]
- rules_only: [{"case_id": "held_out-005", "expected_status": "Inconclusive", "predicted_status": "Inconclusive", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}]
- no_critic: [{"case_id": "held_out-003", "expected_status": "Partially supported", "predicted_status": "Supported", "expected_driver": "outlier_sensitivity", "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}, {"case_id": "held_out-004", "expected_status": "Partially supported", "predicted_status": "Supported", "expected_driver": "window_sensitivity", "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}, {"case_id": "held_out-005", "expected_status": "Inconclusive", "predicted_status": "Supported", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}]
- full: [{"case_id": "held_out-005", "expected_status": "Inconclusive", "predicted_status": "Inconclusive", "expected_driver": null, "predicted_driver": null, "execution_status": "completed", "error_type_correct": false}]

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
