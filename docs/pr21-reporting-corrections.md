# Local PR21 reporting correction proposal

This is an unpushed software correction against a9217a0cd8ee24ad6614dab9b2dba4aafc951431, not a new model experiment or team protocol. Original raw receipts, dataset bytes, prompts, checkers, previous report JSON/figures and the frozen evaluation framework are unchanged.

## Exact planned slots

The canonical report now derives pilot case/arm/repetition slots from the complete recorded split and repetition metadata, and harder-data slots from the fixed 20 cases per size with one no-tools attempt. It rejects duplicates, unplanned or missing slots instead of accepting a matching row count. Legacy harder receipts alone have an explicit implicit no_tools/repetition 0 route; multi-arm receipts cannot exploit that default. Paired summaries reject duplicates and can count wholly missing expected pairs. This rejects incomplete artifacts rather than publishing an attempted-only score as a complete plan.

## Usage separate from answer validity

The CLI envelope is accounted before final-answer parsing. Parse/model/provider errors retain already observed token/cost metadata on their exception and in provider attempt-accounting records. The study-specific adapter attaches these observations to the original harness row; no surgerybench/scorer edit or repaired answer is needed. Malformed output still fails quality checks. Missing token counts remain null independently of observed cost. Costs must be finite, nonnegative and within a software representation bound; missing/invalid values are unknown, not zero.

Reports expose complete cost only when every attempted call has known cost; otherwise cost_usd is null, with known_cost_usd as a lower bound, unknown_cost_runs and cost_coverage. Historical error rows cannot acquire usage that was never saved; their known response subtotals remain visible without fabricating a missing charge. CSP-on-gold and the exact offline MockProvider are explicitly non-model operations with zero model cost.

Both study runners stop scheduling new case work once completed work exposes unknown cost. They retain finished/in-flight rows and skipped-work metadata. This is a fail-closed scheduling guard, not a hard aggregate spending ceiling: already queued case work can finish, the paired runner's work unit includes both arms, and per-call caps/in-flight exposure still require a separately frozen execution protocol. No paid run is authorized by these corrections.

## First attempts versus reruns

Both older size 40/size 80 folders contain all 20 expected cases and meta skipped=0. They are the original recorded attempts, including 36 provider failures. The canonical failure-retaining view now reports these first cohorts: 64/100 evidence-backed successes, 32/50 feasible, 32/50 certified-negative, 36/100 provider errors/UNKNOWN. Sizes5/10/20 remain 20/20 each; initial size 40 is 4/20 and initial size 80 is 0/20.

The later size 40/size 80 reruns remain separate: 38/40 successes, 18/20 feasible, 20/20 certified-negative,one timeout. They repeat 40 original cases and are not 40 additional independent samples. The previous98/100 selected-rerun view remains preserved as historical exploratory output, not the primary failure-retaining cohort.

Known cost subtotals are USD4.060184 for the first cohorts (64/100 runs with complete saved cost), and USD10.764208 for separate reruns (39/40). Neither is a complete bill. These are rescored stored receipts, not fresh model performance or pricing verification.

The code uses explicit HARD_PRIMARY/HARD_RERUNS folder maps; selection is chronological/provenance based, not best-of results. Dataset membership and repetition completeness are checked independently of row count. A reviewed rerun policy is still needed before any prospective experiment. Recommended team choice: retain the initial cohort as primary and publish reruns as clearly labeled supplementary attempts; do not retroactively replace provider failures. This correction does not assert that the team had accepted Allan's model, prompt or budget choices.

The canonical command writes a new framework-summary-v2.json and framework-cost-v2.png, refusing to overwrite an existing summary revision. Historical reports remain in place; their earlier model-only/system-error-excluded diagnostics are not the frozen primary metric. No figure regeneration or live runner is executed by this patch verification.
