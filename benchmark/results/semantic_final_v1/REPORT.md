# Final frozen semantic evaluation

Single scored invocation, 12 cases x 4 variants = 48 recorded outcomes. No case reruns or post-score fixes. Frozen source hashes verified unchanged after scoring.

| Variant | Claim type | Metric | Time/buckets | Segment/confirmation | Tools | End-to-end status |
|---|---:|---:|---:|---:|---:|---:|
| Plain Nemotron | 9/12 (75.0%) | 11/12 (91.7%) | 1/12 (8.3%) | 4/12 (33.3%) | 6/12 (50.0%) | 5/12 (41.7%) |
| Rules-only | 12/12 (100.0%) | 1/12 (8.3%) | 12/12 (100.0%) | 2/12 (16.7%) | 2/12 (16.7%) | 0/12 (0.0%) |
| Model + tools, no Critic | 11/12 (91.7%) | 11/12 (91.7%) | 11/12 (91.7%) | 11/12 (91.7%) | 11/12 (91.7%) | 9/12 (75.0%) |
| Full system | 11/12 (91.7%) | 11/12 (91.7%) | 11/12 (91.7%) | 9/12 (75.0%) | 9/12 (75.0%) | 5/12 (41.7%) |

All accuracy denominators include 12 cases, including errors and unresolved mapping requests. Tool selection measures recommendations, not actual execution. A correct confirmation request is successful ambiguity routing, not a completed Inconclusive verdict.

| Variant | Verdicts completed | Correct automatic | Correct confirmation | Incorrect automatic | Unnecessary confirmation | Execution errors |
|---|---:|---:|---:|---:|---:|---:|
| Plain Nemotron | 7 | 0 | 2 | 7 | 3 | 0 |
| Rules-only | 0 | 0 | 2 | 0 | 10 | 0 |
| Model + tools, no Critic | 9 | 9 | 2 | 0 | 0 | 1 |
| Full system | 7 | 7 | 2 | 0 | 2 | 1 |

Automatic mapping requires exact metric, time column, both buckets, segment and confirmation state; tool variants additionally require mean aggregation. Plain does not expose aggregation, so its six mapping fields are checked. Claim type and tools are scored separately. Correct confirmation counts routing on gold-ambiguous cases, not correctness of every partial field.

## Per-case outcomes

S = Supported; P = Partially supported; I = Inconclusive; C = confirmation required (no verdict); E = execution error. IDs have prefix semantic-final-.

| Case | Expected | Plain | Rules-only | No Critic | Full |
|---|---|---|---|---|---|
| 001: renamed_control | Supported | S | C | S | S |
| 002: business_paraphrase | Supported | C | C | S | S |
| 003: relative_window_control | Supported | C | C | S | I |
| 004: mixed_numeric_causal | Inconclusive | C | C | I | C |
| 005: ambiguous_metric | Inconclusive | C | C | C | C |
| 006: ambiguous_segment | Inconclusive | C | C | C | C |
| 007: mix_reversal | Partially supported | I | C | E | E |
| 008: explicit_segment | Supported | S | C | S | C |
| 009: no_segment_control | Supported | S | C | S | S |
| 010: overall_control | Supported | S | C | S | S |
| 011: explicit_category | Supported | S | C | S | I |
| 012: no_segmentation_control | Supported | P | C | S | S |

## Full versus Rules-only

- Full: metric 11/12 versus 1/12, segment/confirmation 9/12 versus 2/12, tools 9/12 versus 2/12, end-to-end 5/12 versus 0/12. Seven correct automatic mappings versus zero; unnecessary confirmations fall from ten to two.
- Disadvantages: claim type 11/12 versus 12/12, time/buckets 11/12 versus 12/12, and one execution error versus zero. Full does not improve correct ambiguity routing count (both two).
- Full completes cases 001, 002, 003, 009, 010, 011, 012 that Rules-only leaves for mapping. Only 001, 002, 009, 010, 012 match final-status gold. Full unnecessarily requests confirmation for 004 and 008; both variants correctly route 005 and 006. Both leave 007 without a verdict, for different reasons.

## Remaining failures and diagnostic limits

- Case 007 fails with ClaimExtractionError in both tool-assisted model variants before mapper output exists. The saved error is a validation exception from claim extraction; the precise invalid field/raw model output is not retained. Do not infer a specific provider/transport failure. No case rerun was performed.
- Full case 004 maps the columns and buckets correctly but flags comparison_bucket as uncertain; case 008 similarly flags the correctly selected segment. These are unnecessary model uncertainty/confirmation requests.
- Full case 003 has exact mapping, a supported audit (31 to 43), and no failed checks, but 1 of 4 applicable checks is inconclusive and the final status is Inconclusive. Case 011 has exact mapping, a supported audit (27 to 39), no material mix effect, and 3 of 5 checks inconclusive; final status is Inconclusive. These are downstream stability/verdict mismatches against frozen gold, not schema-mapping errors. Saved artifacts do not retain individual Critic receipts, so no more specific check attribution is possible.
- Plain has seven incorrect automatic mappings despite five correct final status labels: final-status correctness alone does not establish correct semantic reasoning.

## Interpretation

There is a measurable benefit from the candidate-constrained model-assisted pipeline over this rules baseline on these 12 cases, especially metric mapping and automatic coverage. Full nevertheless achieves only 5/12 end-to-end status accuracy; no-Critic reaches 9/12. This run does not demonstrate that adding Critic improves final-status accuracy. Variant model calls are independent, so Full/no-Critic differences combine interpretation variability and downstream policy; they cannot all be attributed to Critic.

Small synthetic set, frozen mean/greater scope, exact-match scoring, no general real-world performance claim. Confirmation cases have no final verdict. Model usage is partial and monetary cost unavailable. No analysis rules, prompts, seeds, labels or thresholds changed. Results are sealed with SHA-256 hashes and read-only attributes, not a tamper-proof storage service.
