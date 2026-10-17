# Schema Mapper v1

Claim extraction is separate from schema mapping. The mapper receives the original
claim, extracted claim, column names/dtypes, counts/missingness, and curated values.
It does not compute results or change the extracted claim type. It cannot repair
an upstream extraction error by changing causal/comparison labels.

Numeric metric candidates exclude booleans. ISO calendar columns are preferred as
time candidates; categorical buckets are used only when no ISO time field exists.
Bucket choices are constrained to actual disclosed values, and Python validates
them again against the full dataset. First explicitly mentioned bucket is subject,
second is reference. Unique calendar-month names can map to unique ISO months;
multiple years remain ambiguous. Latest/prior refers to the two latest observed
bins, never today's date. Unsupported ordering requires manual confirmation.

Segments use a distinct categorical field with at least two groups and at least
two nonmissing observations in each selected bucket. Generic groups/segments with
multiple categorical alternatives and vague performance with multiple numeric
metrics require confirmation. Model-declared alternatives/ambiguities also require
confirmation. No forced selection is made. Mean and sum are the only aggregations;
unknown aggregation remains a confirmation task.

No raw rows are sent. ISO date labels and explicitly approved low-cardinality
categories may be disclosed. Identifier-like names and high-cardinality categories
are withheld. This is a disclosure minimization heuristic, not automatic proof
that every category is non-sensitive. The UI requires opt-in for categorical
labels and always retains the manual confirmation form. Existing clients and
Auditor/Investigator/Critic/Verdict rules and thresholds are unchanged.

The schema mapping toggle is optional to preserve offline/manual workflows.
Proposals are never silently audited: the existing audit confirmation remains
required, including calculation type, operator, aggregation and numeric target.
Invalid/model-failed mappings return a sanitized manual-confirmation result.
Short schema-based reasoning_summary is user-facing evidence, not chain-of-thought.

## Evaluation discipline

The original seven semantic cases are now semantic_development. Their IDs/data
and gold labels are unchanged. Historical artifacts retain their original labels
as immutable historical records, but are not held-out evidence going forward.
The per-case pre-change diagnosis is stored separately under
benchmark/results/schema_mapper_v1/old_semantic_failure_analysis.json.

New semantic_held_out seeds 23111–23117 use different fields, wording, values and
calendar buckets. Seven cases: two renamed/paraphrased controls, ambiguous metric,
mixed numeric/causal statement, ambiguous segments, latest/prior control, mix
reversal. Freeze source/prompt/schema hashes and gold/data hashes before the first
scored run. No post-score mapper or prompt adjustments are allowed while that
split remains held out. End-to-end metrics include mapping-required cases as
unresolved; interpretation metrics separately reward correct requests for human
confirmation. Benchmark calculations use their unchanged mean/greater scope.
