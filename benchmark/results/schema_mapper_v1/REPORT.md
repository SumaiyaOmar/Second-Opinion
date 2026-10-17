# Schema Mapper evaluation

Old seven cases: development only. Gold labels unchanged. Frozen held-out inputs and source hashes verified. No post-score prompt/rule changes.

## Development before vs after (not held-out evidence)

| Metric | Before | After |
|---|---:|---:|
| claim_type_extraction_accuracy | 2/7 | 6/7 |
| metric_column_mapping_accuracy | 6/7 | 6/7 |
| time_bucket_mapping_accuracy | 0/7 | 6/7 |
| segment_column_mapping_accuracy | 1/7 | 6/7 |
| correct_tool_selection | 2/7 | 6/7 |
| end_to_end_final_status_accuracy | 0/7 | 4/7 |

## New seven-case held-out results

| Variant | Type | Metric | Time/buckets | Segment/confirmation | Tools | End-to-end |
|---|---:|---:|---:|---:|---:|---:|
| plain | 2/7 | 4/7 | 0/7 | 0/7 | 2/7 | 1/7 |
| rules_only | 7/7 | 1/7 | 6/7 | 2/7 | 2/7 | 0/7 |
| no_critic | 6/7 | 5/7 | 5/7 | 4/7 | 4/7 | 2/7 |
| full | 7/7 | 6/7 | 5/7 | 5/7 | 5/7 | 3/7 |

## Full-system mapping outcomes

Automatic mapping requires exact metric, time/buckets, segment/confirmation and mean aggregation. Claim type/tool selection are scored separately. Correct confirmation means a mapping_required response on a gold-ambiguous case; it does not imply all proposed fields are correct.

- development/correct_automatic_mappings: 4 (semantic-001, semantic-002, semantic-004, semantic-006).
- development/incorrect_automatic_mappings: 0 (none).
- development/correct_confirmation_requests: 2 (semantic-003, semantic-005).
- development/unnecessary_confirmation_requests: 0 (none).
- development/execution_errors: 1 (semantic-007).
- held_out/correct_automatic_mappings: 3 (semantic-held-out-001, semantic-held-out-004, semantic-held-out-007).
- held_out/incorrect_automatic_mappings: 1 (semantic-held-out-006).
- held_out/correct_confirmation_requests: 2 (semantic-held-out-003, semantic-held-out-005).
- held_out/unnecessary_confirmation_requests: 1 (semantic-held-out-002).
- held_out/execution_errors: 0 (none).

## Remaining full-system failures and unresolved cases

- {"role": "development", "case_id": "semantic-003", "execution": "mapping_required", "expected_status": "Inconclusive", "predicted_status": null, "mismatches": []}
- {"role": "development", "case_id": "semantic-005", "execution": "mapping_required", "expected_status": "Inconclusive", "predicted_status": null, "mismatches": []}
- {"role": "development", "case_id": "semantic-007", "execution": "error", "expected_status": "Partially supported", "predicted_status": null, "mismatches": ["claim_type", "metric_column", "group_column", "left", "right", "segment_column", "needs_confirmation", "tool_selection"]}
- {"role": "held_out", "case_id": "semantic-held-out-002", "execution": "mapping_required", "expected_status": "Supported", "predicted_status": null, "mismatches": ["metric_column", "group_column", "left", "right", "needs_confirmation", "tool_selection"]}
- {"role": "held_out", "case_id": "semantic-held-out-003", "execution": "mapping_required", "expected_status": "Inconclusive", "predicted_status": null, "mismatches": ["group_column", "left", "right"]}
- {"role": "held_out", "case_id": "semantic-held-out-005", "execution": "mapping_required", "expected_status": "Inconclusive", "predicted_status": null, "mismatches": []}
- {"role": "held_out", "case_id": "semantic-held-out-006", "execution": "completed", "expected_status": "Supported", "predicted_status": "Inconclusive", "mismatches": ["segment_column", "tool_selection"]}

## Limitations

Seven held-out cases are a small controlled sample. Mapping-required cases remain unresolved end-to-end, while appropriate human routing is counted separately. Extraction errors cannot be repaired by the mapper. These cases share a mean/greater analytical scope. No analytical thresholds were changed. Mapper/verification explanation token usage is partial. Candidate/sample disclosure is minimized but not a general automatic privacy classifier.
