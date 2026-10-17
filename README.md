# Second Opinion — AI Data Truth Engine

**An analyst that doubts itself.**

Most AI analytics tools answer questions. Second Opinion asks whether the answer should be trusted.

## Overview

Second Opinion is an AI-assisted analytics review tool. Upload a CSV and a business claim to verify its numbers, investigate hidden segment patterns, challenge the conclusion, and inspect the evidence behind a qualified verdict.

## The problem

A correct aggregate number can support a misleading story. Changing group composition, outliers, selective time windows, small samples, and unsupported causal interpretations can undermine an apparently convincing conclusion. Fluent AI explanations alone do not resolve these issues.

## What Second Opinion does

- Extracts a structured claim and proposes mappings to actual dataset fields.
- Requests human confirmation when mappings are ambiguous.
- Checks supported numeric and comparison claims with deterministic calculations.
- Examines segment trends and composition shifts where applicable.
- Runs a fixed stress-test battery and preserves failed or inconclusive checks.
- Produces a verified conclusion with limitations and computational receipts.

## Workflow

**Claim → Map → Audit → Investigate → Stress-test → Verdict**

Each stage uses stored upstream evidence. Users confirm mappings and explicitly run the analytical stages; loading the demo does not start analysis.

## How it works

1. **Claim:** interpret the original statement into a validated structured representation.
2. **Map:** match business concepts to available columns and observed bucket values. Python validates proposals; unresolved fields require confirmation.
3. **Audit:** recompute an overall metric or compare two periods/groups using confirmed inputs.
4. **Investigate:** compare segment metrics and shares, decompose composition effects, and detect aggregate-versus-segment direction reversals.
5. **Stress-test:** test sensitivity using frozen rules, reporting held, failed, inconclusive, or not-applicable outcomes.
6. **Verdict:** synthesize existing structured evidence without independently recalculating metrics. Python fixes the status before optional model wording.

## Architecture

The Streamlit interface coordinates a modular Python pipeline. `core/` contains claim interpretation, schema mapping, stage orchestration, and verdict synthesis. `tools/` contains deterministic analytics, chart data, and receipt helpers. `ui/` handles presentation and session-state dependencies. `benchmark/` separates frozen cases, predictions, and evaluation artifacts.

## Role of NVIDIA Nemotron-3.5-Lightning

The OpenAI-compatible model identifier is `nvidia/Nemotron-3_5-Lightning`. Nemotron interprets claims, proposes candidate-constrained schema mappings, supports tool/test selection, and explains evidence. Its output is validated before use. Verdict wording is restricted to approved evidence-based alternatives; unavailable or rejected wording falls back to deterministic text.

## Role of Nebius Token Factory

Nebius Token Factory hosts the model inference endpoint used through the OpenAI Python client: `https://api.tokenfactory.nebius.com/v1/`. Local credentials authorize inference; they are not part of the repository or computational evidence.

## What the AI does vs what deterministic Python does

| AI assistance | Deterministic Python |
|---|---|
| Interpret natural-language claims | Validate structured outputs and actual column/bucket selections |
| Propose schema mappings and relevant tests | Calculate metrics, differences, segment shares, and mix effects |
| Explain supplied evidence | Run stress tests, determine findings and final status |
| Rewrite a conclusion within approved evidence | Build chart data, receipts, and benchmark metrics |

The model does not calculate reported numbers, establish causes, or assign confidence percentages.

## Verdict types

| Status | Meaning |
|---|---|
| Supported | Evidence supports the assertion within the audited scope and applicable checks hold. |
| Partially supported | The numeric result has material qualifications, such as composition effects or failed sensitivity checks. |
| Unsupported | The deterministic calculation contradicts the audited assertion. |
| Inconclusive | Required evidence is missing, unresolved, invalid, or insufficiently stable. |

A failed stress test does not automatically make a claim Unsupported. Exact ordered decisions are documented in [VERDICT_RULES.md](VERDICT_RULES.md).

## Stress tests

The fixed battery includes an adjacent/expanded time-window check, leave-one-segment-out analysis, pooled 1.5×IQR outlier removal, mean-versus-median comparison, and seeded bootstrap resampling where applicable. Bootstrap requires at least 20 observations per bucket and uses 1,000 resamples with seed `20261016`.

Results report counts such as “Held 1 of 4 applicable checks,” alongside failures and inconclusive checks. They are not truth scores. Preconditions and exact thresholds are documented in [STRESS_TEST_RULES.md](STRESS_TEST_RULES.md).

## Computational receipts / evidence

Charts use Python-calculated values. Expandable proof includes calculation names, columns, filters/buckets, row counts, aggregations, computed values, formulas or rules, results, limitations, and dataset fingerprints where available. Raw structured evidence remains accessible without dominating the main interface.

## Simpson’s paradox / mix-shift demo

Click **Try demo case** to load [data/synthetic_simpson.csv](data/synthetic_simpson.csv) and prefill:

> The overall score increased after the change.

Then click **Analyze claim**, confirm the comparison, and continue through Investigation, Stress Test, and Verdict.

| Evidence | Before | After |
|---|---:|---:|
| Aggregate mean score | 36 | 74 |
| High segment mean | 90 | 80 |
| Low segment mean | 30 | 20 |
| High segment share | 10% | 90% |

The aggregate improvement is numerically correct while both segments decline. The expected qualified verdict is **Partially supported**: the aggregate increase is consistent with changing segment composition rather than improved within-segment performance. This observational pattern does not prove a causal explanation. The app calculates these results through the existing pipeline; loading the demo does not hard-code a verdict.

## Evaluation

The final frozen semantic evaluation contains **12 held-out cases**, evaluated across four variants. These are saved results, not a new evaluation run.

| Measure | Frozen result |
|---|---:|
| Full system metric mapping | 11/12 |
| Full system time/bucket mapping | 11/12 |
| Full system correct automatic mappings | 7 |
| Full system correct confirmation requests | 2 |
| Full system incorrect automatic mappings | 0 |
| Full system end-to-end status accuracy | 5/12 |
| Rules-only end-to-end status accuracy | 0/12 |
| Model + tools, no Critic end-to-end status accuracy | 9/12 |

The benchmark is **small and synthetic** and does not establish broad real-world superiority. Rules are strong once mappings are already known; model assistance mainly improves interpretation of messy claims and schemas. The rules-only end-to-end result includes cases awaiting manual mapping, so it is not a measure of calculation accuracy given correct mappings.

The Critic can over-abstain. Adding it did not improve final-status accuracy in this run; independent model calls also introduce interpretation variability between variants. One execution failure occurred in each tool-assisted model variant on the same case, during claim extraction. The saved artifacts do not establish a specific provider/transport cause.

Correct confirmation requests measure ambiguity routing, not completed verdicts. All accuracy denominators include all 12 cases, including errors and unresolved confirmations. Earlier semantic sets are development evidence and must not be presented as independent held-out validation.

See the [frozen final report](benchmark/results/semantic_final_v1/REPORT.md) for all four variants, per-case failures, scoring definitions, and limitations. The frozen case manifest is [semantic_final_held_out_v1.json](benchmark/frozen/semantic_final_held_out_v1.json).

## Limitations

- The deterministic toolbox supports a limited family of overall and two-period/two-group numeric comparisons, not arbitrary analytical questions.
- Ambiguous schemas need human confirmation; automatic interpretation can fail or ask unnecessary questions.
- Segment investigation assumes suitable observation granularity and sufficient usable groups; pre-aggregated rates require care and are not a general supported substitute for individual observations.
- Missing data, small samples, unavailable adjacent time bins, and unresolved stability checks can produce Inconclusive results.
- Bootstrap uses IID resampling; it does not establish causal validity or address every dependency structure.
- Observational associations and mix shifts do not prove the “true cause.”
- The current evaluation is narrow; no general production reliability or real-world superiority claim is justified.
- Claim text and selected schema information are sent to the inference provider. Use non-sensitive inputs and review schema-sharing controls.

## Tech stack

Python, Streamlit, pandas, NumPy, python-dotenv, the OpenAI Python client, Nebius Token Factory, and NVIDIA Nemotron-3.5-Lightning. Dependencies are listed in [requirements.txt](requirements.txt).

## Local setup

Use Python 3.11 (the interpreter used for local testing). From the project root:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Environment variable setup

Store `NEBIUS_API_KEY` in a local `.env` file at the project root:

```dotenv
NEBIUS_API_KEY=
```

Fill the empty value with your own key locally. Never commit or share it. `.env` is ignored by Git; the blank example above contains no secret. Model-assisted stages require a valid key; deterministic calculations remain Python-based.

## Run command

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit. For the project tests:

```bash
python -m unittest discover -s tests
```

The connectivity test can make a live API call and requires configured credentials. Tests are separate from benchmark scoring; do not regenerate or rescore frozen evaluation artifacts to reproduce the published report.

## Repository structure

```text
app.py                         Streamlit entry point
core/
  claims.py                    Structured claim extraction
  schema_mapper.py             Candidate-based semantic mapping
  schema_mapping_validation.py Deterministic mapping validation
  auditor.py                   Audit request construction
  investigator.py              Segment investigation orchestration
  critic.py                    Fixed stress-test battery
  verdict.py                   Evidence-only verdict synthesis
  nebius_client.py             Nebius inference client
tools/
  analytics.py                 Deterministic calculations
  visuals.py                   Evidence chart data
  receipts.py                  Computational receipts
ui/                            Presentation, styling, and state helpers
data/synthetic_simpson.csv     Demo dataset
benchmark/                     Cases, evaluation runner, frozen results
tests/                         Analytical and UI regression tests
requirements.txt               Python dependencies
STRESS_TEST_RULES.md            Frozen stress-test rules
VERDICT_RULES.md                Deterministic verdict decisions
```

## Future work

Broaden documented real-case evaluation, improve ambiguity handling and execution diagnostics, examine Critic over-abstention on development evidence, and support more calculation families with explicit assumptions. Any changes to prompts or rules should be evaluated on newly frozen held-out cases rather than tuning against the published final split.
