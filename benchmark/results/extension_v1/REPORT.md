# Documented and semantic extension v1

Original result artifacts unchanged: True (8 files).
No thresholds were tuned on these cases. Development results are not independent evidence.

## Final-status accuracy across splits

| Variant | Held-out synthetic | Documented kidney-stone | Semantic end-to-end |
|---|---:|---:|---:|
| plain | 2/6 | 1/1 | 0/7 |
| rules_only | 6/6 | 1/1 | 4/7 |
| no_critic | 3/6 | 1/1 | 1/7 |
| full | 6/6 | 1/1 | 0/7 |

## Semantic interpretation

Exact matches; API/malformed responses are incorrect. Mapping-required cases have no final verdict, are excluded from conditional analytical accuracy, and remain unresolved in end-to-end accuracy.

| Variant | Claim type | Metric | Time/buckets | Segment/confirmation | Recommended tools | End-to-end |
|---|---:|---:|---:|---:|---:|---:|
| plain | 2/7 | 6/7 | 0/7 | 1/7 | 2/7 | 0/7 |
| rules_only | 7/7 | 6/7 | 7/7 | 6/7 | 6/7 | 4/7 |
| no_critic | 1/7 | 4/7 | 0/7 | 0/7 | 1/7 | 1/7 |
| full | 2/7 | 6/7 | 0/7 | 1/7 | 2/7 | 0/7 |

## Mapping required

- plain: semantic-001, semantic-002, semantic-003, semantic-004, semantic-006
- rules_only: semantic-002, semantic-003, semantic-005
- no_critic: semantic-001, semantic-003, semantic-004, semantic-007
- full: semantic-002, semantic-003, semantic-004, semantic-005, semantic-006

## Full-system failures and unresolved cases

- held_out/held_out-005: execution=completed; expected=Inconclusive; predicted=Inconclusive; interpretation mismatches=[]; error label correct=False.
- semantic/semantic-001: execution=completed; expected=Supported; predicted=Inconclusive; interpretation mismatches=['claim_type', 'group_column', 'left', 'right', 'segment_column', 'tool_selection']; error label correct=False.
- semantic/semantic-002: execution=mapping_required; expected=Supported; predicted=None; interpretation mismatches=['claim_type', 'group_column', 'segment_column', 'needs_confirmation']; error label correct=False.
- semantic/semantic-003: execution=mapping_required; expected=Inconclusive; predicted=None; interpretation mismatches=['claim_type', 'metric_column', 'group_column', 'segment_column', 'tool_selection']; error label correct=False.
- semantic/semantic-004: execution=mapping_required; expected=Inconclusive; predicted=None; interpretation mismatches=['group_column', 'segment_column', 'needs_confirmation', 'tool_selection']; error label correct=False.
- semantic/semantic-005: execution=mapping_required; expected=Inconclusive; predicted=None; interpretation mismatches=['claim_type', 'group_column', 'segment_column']; error label correct=False.
- semantic/semantic-006: execution=mapping_required; expected=Supported; predicted=None; interpretation mismatches=['group_column', 'segment_column', 'needs_confirmation', 'tool_selection']; error label correct=False.
- semantic/semantic-007: execution=completed; expected=Partially supported; predicted=Inconclusive; interpretation mismatches=['claim_type', 'group_column', 'tool_selection']; error label correct=False.

## Documented-case caution and limitations

Source: Charig et al., BMJ 1986, DOI 10.1136/bmj.292.6524.879, PMID 3083922. Publisher metadata/aggregate counts checked; stone-size cells supplied explicitly by the user and corroborated by the cited teaching transcription. The input is observational count data, anonymously expanded into binary outcomes; no treatment's causal superiority is established.
The unchanged correction template can use temporal 'declined' for non-temporal treatment contrasts. The unchanged pooled-IQR rule can remove valid binary failures. Both are documented limitations, not reasons to tune this evaluation.
One documented example and seven synthetic semantic cases are too few for broad claims. Semantic recommended-tool accuracy is not executed-tool accuracy; no-Critic still omits Critic. A fixed mean/greater scaffold means aggregation/operator interpretation is not evaluated. Conditional accuracy must be read with mapping coverage and end-to-end accuracy. See each split's JSON/CSV for every variant's failures and source hashes.
