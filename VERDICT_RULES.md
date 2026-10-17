# Verdict v1: ordered deterministic rules

The Verdict stage receives structured claim, audit, optional investigation, and
Critic results only. It never receives a DataFrame or recomputes a metric.
Apply the first matching rule:

1. **R1 Inconclusive**: absent/blank original claim, invalid audit status, or a
   resolved audit without finite overall or left/right computed values.
2. **R2 Inconclusive**: Auditor status is Inconclusive.
3. **R3 Unsupported**: Auditor status is Unsupported. Subsequent sensitivity
   results or missing later stages cannot upgrade a numerically contradicted claim.
4. **R4 Inconclusive**: a supplied Investigator is invalid or inconclusive.
   Omitting an Investigator is allowed (including when not applicable), with an
   explicit limitation that support covers the audited scope only.
5. **R5 Inconclusive**: Critic is missing, malformed, lacks the five unique checks,
   has inconsistent counts, or has no held/failed applicable check. An entirely
   unresolved battery is insufficient. Not-applicable checks are excluded.
6. **R6 Partially supported**: Auditor is Partially supported, Investigator reports
   direction_reversal or mix_shift, or at least one stress check failed. This rule
   precedes remaining inconclusive checks: resolved numerical support with known
   qualifications is reported as partial, with every failed/unresolved check shown.
7. **R7 Inconclusive**: otherwise any applicable Critic check remains inconclusive.
8. **R8 Supported**: otherwise the audit supports the assertion, all applicable
   checks held, and there is no contradictory investigation evidence.

A stable Unsupported audit stays Unsupported. A numerically true aggregate with
segment reversal stays numerically true and receives Partially supported, not
Unsupported. No confidence score is created; no stress result is hidden.

## Corrected wording and failure handling

Python freezes the status and builds equivalent corrected-conclusion candidates
from copied numeric audit evidence, investigation findings, and stress statuses.
Nemotron uses the existing `nvidia/Nemotron-3_5-Lightning` client to choose the
clearest candidate through an enum-constrained JSON response. Exact membership is
validated locally. Each candidate retains the same facts, uncertainty and caveats;
the model cannot insert new numbers or causal statements or omit qualifications.
Free-form paraphrasing is intentionally excluded because its factual entailment
cannot be guaranteed with a numeric-token check alone.

On timeout, authentication/provider error, malformed JSON, or unapproved prose,
the deterministic corrected statement is returned with the unchanged status and
a sanitized fallback receipt. Provider error text and credentials are not shown.

## Limits

This stage trusts the supplied structured evidence and its upstream mappings;
without raw data it cannot independently authenticate a dataset or rerun receipts.
The UI invalidates cached verdicts when claim, dataset, audit, investigation, or
Critic results change. Inconclusive results are deliberately conservative.
Numeric direction does not by itself establish business improvement or causation.
The rewrite is constrained composition, not unrestricted model-authored prose.
