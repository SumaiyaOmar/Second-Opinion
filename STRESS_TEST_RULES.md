# Critic v1: frozen sensitivity rules

All numbers and findings are computed by Python. Held means stable under one
specified perturbation, not that a claim is true. Unsupported claims can remain
stably unsupported. Failed and inconclusive results remain visible.

- Preconditions: a fresh matching audit, complete finite selected metric values,
  and at least two observations in each evaluated bucket. Missing prerequisites
  produce inconclusive checks. Overall audits compare with the confirmed target;
  comparison audits use left minus right. Numerical tolerance is
  `1e-9 * max(1, absolute aggregate values, absolute target)`.
- Alternative window: only confirmed two-period comparisons whose column uses
  a consistent ISO `YYYY-MM` or `YYYY-MM-DD` format. Original bins must be adjacent
  in sorted observed bins. Expand the earlier bucket with its immediate predecessor
  and the later bucket with its immediate successor. Require both neighbors; never
  select windows by metric outcomes. Missing calendar bins are not synthesized.
- Leave one segment out: requires a separately confirmed segment column. Remove
  every observed selected segment once. Recompute each trial. Fewer than two
  remaining observations in a bucket is inconclusive; never silently drop trials.
- Outliers: use pooled original-bucket observations, linear 25th/75th percentiles,
  and inclusive `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]` bounds. At least four pooled rows
  are required. With zero IQR the same fixed rule applies. Thresholds are not tuned.
- Mean versus median: mean audits only. Fail on changed direction/assertion or
  a delta difference greater than `max(numerical tolerance, 50% * abs(original delta))`.
- Bootstrap: at least 20 observations per original bucket, 1,000 independent IID
  resamples preserving each bucket's size, NumPy default RNG seed `20261016`.
  Return the linear 2.5th/97.5th percentile interval of aggregate difference
  (or overall minus target). Held if the interval preserves original direction;
  failed if entirely opposite; spanning zero is inconclusive. This is not a
  confidence score. Exact comparison magnitudes are not validated by this interval.
- If a completed Investigator result is supplied, dataset perturbations also
  recompute its categorical finding. Changed findings fail; inability to recompute
  is inconclusive unless an aggregate sensitivity already fails. Median and
  bootstrap do not validate mean-based mix decomposition; report inconclusive
  for that scope rather than claiming the investigation held.

The summary counts all five entries, excludes not-applicable entries from the
applicable denominator, and includes inconclusive entries in it. No final verdict
is upgraded by passing stress tests. Row-volume changes can mechanically change
sums. The bootstrap assumes independent equally weighted observations and does
not account for clustering, repeated entities, or serial dependence.
