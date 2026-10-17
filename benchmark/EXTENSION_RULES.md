# Documented and semantic evaluation v1

Original benchmark result directories are preserved. New runs belong under
`results/extension_v1/{held_out,real_documented,semantic}`. Do not tune on these
evaluation cases. The existing development/held-out seeds, analysis defaults,
stress thresholds and verdict rules are unchanged.

The kidney-stone manifest contains bibliographic provenance, DOI, observational
caution and a locally transcribed four-cell success/denominator table. Binary
expansion reproduces the success rates exactly but is not recovered patient-level
data. Source metadata/aggregate counts were verified at implementation time;
benchmark runs contain no external source retrieval. The documented comparison
must never be interpreted as proof of treatment superiority. Standard stress rules
are retained even when IQR filtering of a binary outcome is not scientifically
meaningful; its failures must remain visible.

Seven semantic cases use frozen seeds 12101–12107. Inputs have conv_pct, grp,
wave, schema descriptions, and no confirmed mappings. Cases cover clear aliases,
a business paraphrase, ambiguous metric, mixed numeric/causal claim, ambiguous
segments, unusually worded clean control, and a requested cohort/mix comparison.
Labels are fixed in metadata before prediction. Descriptions and categorical
bucket values are available equally to all variants. Rules-only uses generic
column aliases/month matching and literal affirmative causal verbs; it is able
to solve straightforward controls and explicitly asks for mapping elsewhere.
Model-based variants map/extract with one schema-constrained call. Plain additionally
predicts the status without tools. Tool variants reuse the existing analytical
pipeline after interpretation; no extra model extraction is silently performed.
No-Critic still omits Critic and uses its prior ablation decision policy.

Interpretation metrics are separate exact-match rates for claim type, metric
column, time column plus ordered buckets, segment column plus confirmation flag,
and recommended tool set. The tools are recommendations for the full workflow,
not evidence that the ablated variant executed them. A fixed mean/greater scaffold
is shared across these all-increase semantic cases; general aggregation/operator
interpretation is not evaluated by this small split.

`mapping_required` has no final verdict and is not an analytical failure or an
analytical abstention. Conditional analytical metrics exclude such cases. Separate
end-to-end accuracy includes them as unresolved, and exact confirmation/tool
metrics can reward the correct request for clarification. Missing API responses
are not rewarded for matching null fields. Plain and model-tool runtime failures
remain visible. Full-system failure lists include both wrong conclusions and
unresolved mapping cases (reported separately).

Run all four variants with `--variant all --live --workers 4` and one of
`--split held_out`, `--split real_documented`, or `--split semantic`; always choose
a new output directory to preserve prior runs. A tiny controlled sample cannot
establish broad model superiority. No thresholds or baseline dictionaries are to
be revised in response to these evaluation results.
