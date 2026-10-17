# Frozen benchmark v1

Run a deterministic baseline:

```powershell
python -m benchmark.run --split development --variant rules_only --output benchmark/results/development
```

Run all four variants on the held-out split (live API calls):

```powershell
python -m benchmark.run --split held_out --variant all --live --workers 4 --output benchmark/results/held_out
```

Without `--live`, model variants are explicitly `not_run`, never silently replaced
by rules-only predictions. Outputs: results.json, results.csv, summary.json,
summary.md. Runtime/API failures are retained and do not count as correct abstentions.

## Cases and label isolation

Development seeds: 1103–1108. Held-out seeds: 8101–8106, in this frozen order:
Simpson, causal, outlier, window, insufficient, clean. One case per type per split.
Seeds control row order and a small common metric offset, preserving the designed
counterexample. This is a deliberately small, structurally matched evaluation,
not a statistically independent broad test set. Do not tune on held-out results.
Only development results may be used for debugging. Do not use development
performance for headline claims. No statistical significance is claimed.

Gold labels live in BenchmarkCase.metadata, separate from AnalysisInput passed
to predictors. Expected labels are fixed before predictions. Generated DataFrames
and confirmed mappings are shared equally; case IDs, types, seeds and expected
labels never enter model prompts or analytical calls.

Gold outcomes: Simpson/outlier/window = Partially supported; causal/insufficient =
Inconclusive with abstention; clean = Supported. Causal cases are observational:
the system's unsupported-analysis scope should abstain, not pretend causality was
numerically disproved. Expected drivers: mix_effect, outlier_sensitivity,
window_sensitivity; none for causal, insufficient, clean.

## Variants

- plain: Nemotron gets the claim, confirmed mappings, generic descriptive profile
  and complete records, but no deterministic analytical tools or tool results.
- rules_only: a frozen literal causal/comparison parser, existing Audit,
  optional Investigation, Critic and deterministic Verdict; no model calls.
- no_critic: model claim extraction + Audit + optional Investigation. Its frozen
  ablation status is the audit status, downgraded to partial for reversal/mix and
  inconclusive for an unresolved requested Investigation. No Critic or final
  Verdict call is made; missing Critic is not accidentally treated as evidence.
- full: model extraction + Audit + optional Investigation + Critic + Verdict,
  including the existing validated Nemotron correction/fallback behavior.

No analytical, verdict, stress or visual rules are changed. The fixed benchmark
error adapter maps reversal/mix to simpson; failed outlier/median to outlier;
failed window to window; unsupported causal scope to causal; entirely unresolved
stress/audit evidence to insufficient. Driver priority is mix, outlier, window.
This adapter consumes only predictions. Detection, exact error-class correctness,
status correctness and rank-1 driver correctness are reported separately.

All existing thresholds remain frozen in STRESS_TEST_RULES.md and VERDICT_RULES.md
and the Investigator defaults (2 rows/segment/bucket, 10% materiality, 1e-9 scaled
tolerance). Model temperature is zero; provider reproducibility is not guaranteed.
Token usage is recorded when available. Verdict explanation usage is unavailable,
so full-system token counts are explicitly partial. Price/cost remains null; no
external pricing is fetched. No credentials or raw provider errors are persisted.

## Locally documented real cases

`documented/manifest.json` now includes the observational kidney-stone comparison,
with locally stored published count cells, provenance and binary expansion notes.
See EXTENSION_RULES.md for the separate frozen semantic evaluation and mapping metrics.
Do not label the existing synthetic Simpson fixture as real. Add further entries with
`source_citation`, `transcription_notes`, local `csv_path`, `claim`, `mapping`,
`segment_column`, and `metadata` containing case_id, case_type, expected_status,
expected_error_type, expected_driver, should_abstain, is_clean_control,
generation_seed (null for non-generated cases). Run with `--split real_documented`.
Public examples must be source-verified before any headline real-data claim.
