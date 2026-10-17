# Targeted mapper reliability round

This round uses only the previously recorded mapper-v1 failures. Both historical
seven-case semantic sets are development evidence from now on. Existing result
files, frozen historical manifests, case data, seeds and gold labels are unchanged.
`semantic_held_out` is now a development alias for `semantic_mapper_development`;
its old name must not be reported as new held-out evidence.

## Segment acceptance

The validator accepts a proposed segment only for explicit/implicit grouping
language, extracted entity names matching actual categorical values, an explicit
upstream segmentation request, or user confirmation. Otherwise it sets the segment
to null, removes irrelevant segment alternatives, and marks the field not_required.
User-confirmed choices still require existing compatible columns and usable groups.
No Auditor, Investigator, Critic or Verdict formulas or thresholds are changed.

## Independent recovery and confirmation

Each metric, time field, baseline bucket, comparison bucket, segment and aggregation
has an independent validity status/reason. Invalid fields are rejected without
erasing valid siblings. Multiple plausible candidates affect only their role.
Bucket validity depends on a validated time field; segment usability depends on
confirmed buckets. Confirmation_fields lists only unresolved/ambiguous required
fields. Model semantic uncertainty is field-local via uncertain_fields, not a
global instruction to erase the mapping. Free-form ambiguity prose does not
invalidate unrelated fields.

On absent/malformed output, recover unique literal metric names, a unique ISO
time field with claim-matched buckets, and explicit mean/total wording. This does
not guess unknown business synonyms or an unspecified aggregation. The manual
confirmation form remains available and recovered values remain prefilled.

## Authoritative explanation and diagnostics

Python builds reasoning_summary entirely from the post-validation structured
fields and statuses. Model rationale text is discarded. Invalid/rejected names
and invented buckets cannot appear in the summary. No hidden chain-of-thought is
requested or displayed.

Internal diagnostics contain only fixed reason codes and field names:
provider_error, malformed_output, schema_validation_failure,
candidate_validation_failure. Raw provider errors, response bodies and credentials
are not retained. A fallback can have recoverable valid fields as well as a
failure diagnostic; it is not mislabeled as a new analytical result.

## New final semantic set (not scored)

`semantic_final_held_out`: 12 cases, seeds 34101–34112, different fields, wording,
2031 calendar buckets and metric values. Composition: six unsegmented clean
controls (including relative-time and explicit no-segmentation wording), two
explicit segmentation controls, one mix reversal, one mixed numerical/causal
claim, one ambiguous metric and one ambiguous segment case.

Freeze with `python -m benchmark.freeze_final_mapper` after regression tests pass.
Freezing generates/hashes inputs, gold and source only; it never invokes a
predictor or API. The manifest records scored_at_freeze=false. A future scoring
run must verify those hashes first. No final held-out evaluation is authorized
or run as part of this reliability task. Any future post-score tuning requires
reclassifying that set as development and creating another held-out set.
