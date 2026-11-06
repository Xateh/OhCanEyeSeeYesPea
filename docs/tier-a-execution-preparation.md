# Offline execution-contract preparation proposal

This additive extension does not change `tier_a_contract.py`, its strict receipt
schema, the hashed scheduling package or any export. It is not team acceptance
or an approved execution plan. No provider runner, tool invocation, network path,
pricing adapter, output writer or model evaluation is implemented.

`tier_a_execution_contract.validate(directory, manifest, receipts, shared_prompt,
output_prompt)` verifies execution metadata, then delegates scoring receipts to
the existing validator/scorer unchanged. Any successful result is marked
`proposal_only` and `execution_authorized=false`, including a complete synthetic
fixture. There is no approval flag that can enable execution.
Main now contains the team-agreed scoring freeze in `evaluation-framework.md`.
This preparation extension does not supersede that agreement or implement its
remaining execution protocol. In particular, it preserves the original scorer's
completion semantics; reconciling those with the framework is a separate change.

## Provisional manifest

Required exact keys are `version`, `status`, `run_id`, `scoring_plan`,
`corpus_hashes`, `provider_revision`, `model_revision`, `consumer_sha256`,
`execution_contract_sha256`,
`shared_prompt_sha256`, `output_prompt_sha256`, `tool_schema_sha256`,
`tool_revision`, `limits`. Version is
`tier-a-execution-preparation-proposal-v1`, status is `proposal_only`.
`scoring_plan` uses the unchanged existing proposal schema. Its R must be 1:
the nine eligible cases produce 18 planned arm-attempts, not a statistical study.
All six oracle-only negatives remain excluded. This envelope is proposed only.
The manifest does not yet freeze temperature/seed, arm order or retry policy.

`corpus_hashes` must exactly match the four reviewed export hashes already pinned
by the scorer. `bindings(shared_prompt, output_prompt)` computes the actual
consumer source SHA-256, byte-level UTF-8 shared/output prompt SHA-256 values,
canonical existing CSP tool-definition hash, and existing tool revision. The
provenance also includes `execution_contract_sha256`, binding this execution and
budget-accounting module separately from the unchanged scorer. These hashes pin
source bytes, not independent source authenticity or research approval. Prompt
text must be explicitly supplied and bounded to 64 KiB each; no experimental
prompt content is selected here. Provider/model revisions must be explicit,
nonempty strings, not null/unknown/TBD. Opaque provider identities cannot be
verified against an actual service by offline validation.

Limits have exactly these keys; an incomplete preparation template is:

```json
{
  "tokens_per_attempt": null,
  "wall_seconds_per_attempt": null,
  "spending_ceiling_usd": null,
  "max_csp_calls": 4
}
```

The nulls deliberately fail validation. Explicit positive integer token limit,
positive finite wall-clock limit <=60 seconds and positive finite decimal-text
USD ceiling must be supplied before a future runner could even consider start.
The spending ceiling is for the complete proposed smoke, tokens/wall time per
arm-attempt. No value is chosen as a team budget by this implementation. The
four-call CSP cap mirrors the existing bounded tool interface; no-tools allows
zero calls. A future agreed protocol could require a separately versioned change.
The 60-second shell command envelope is a local offline verification limit, not
a team-approved per-attempt research budget. This prototype's <=60-second field
cap is provisional software validation only; actual research limits are undecided.

## Receipt extension

Each exact-key wrapper includes `attempt_id`, `run_id`, all eight revision/prompt/
schema identities (`provider_revision`, `model_revision` and six binding keys),
`scoring_receipt`, `elapsed_seconds`, `usage`, `usage_unknown_reason`, `spend_usd`,
`spend_unknown_reason`, `termination_cause`, `tool_calls`, `tool_count`.
Run/attempt IDs are ASCII alphanumeric/underscore/hyphen, 1..64 characters.
Attempt IDs and eligible case/repetition/arm slots must be unique within a batch;
cross-batch durable IDs, resume and retry policy remain unimplemented.
Aggregate attempt metadata and tool-name/count records are not an ordered
per-call provenance ledger. No cross-batch resume or retry semantics are implied.

Elapsed time is finite nonnegative seconds. Usage is exactly nonnegative integer
`input_tokens` and `output_tokens`, with null unknown reason, or usage=null with
a nonempty explicit reason. Booleans do not count as integers. Spending is finite
nonnegative decimal text with null unknown reason, or null with an explicit reason.
Unknown values are never fabricated as zero. A known spending subtotal above the
ceiling is retained and flagged; unknown spending prevents complete budget evidence.
Reported usage/spend is not independent billing or pricing verification.
USD text permits at most 12 whole and 8 fractional digits, without exponents;
this keeps the bounded 18-receipt Decimal subtotal exact and rejects NaN/Infinity.

Termination causes map explicitly to unchanged scoring termination:
`completed` -> final; `abstained` -> abstained; `provider_error`/`provider_timeout`
-> provider_error; `tool_error`/`tool_timeout` -> tool_error. Existing scoring flags
must still agree. Tool records are exactly `name` and `schema_sha256`; only CSP
in the CSP arm is allowed, with count equal to list length and at most four.
These records do not invoke tools or assert that translated inputs were correct.
The fifth call, schema drift and forbidden tool names fail closed.

Malformed metadata, routing or duplicate violations reject the whole extension
request with a diagnostic. Genuine time/token/spending overruns in structurally
valid receipts are retained, never discarded or automatically rerun. Each affected
planned row has explicit `budget_violations` and `budget_error`, remains attempted,
and cannot earn preparation-layer feasible/certified/task success. The original
scorer's success is retained as `unadjusted_scorer_success`. It already includes
operational-failure gating, so it is not a pure evidence-validity indicator.
Arm/family metrics and paired outcomes are recomputed with original denominators;
`budget_error_rate` reports violations over planned slots. Input raw receipts,
termination, output-error flags and decision-agreement diagnostics remain intact.
Since spending is an aggregate rather than an ordered ledger, exceeding the
batch ceiling conservatively flags every recorded attempt, without inventing a
chronological cutoff or attributing spend to an individual attempt. Raw/normalized
output disagreement is handled by the unchanged scorer, retaining the attempted
slot and its output error. Missing receipts retain all 18 planned slots and pair
missingness. Results retain manifest/extension snapshots and scoring results.
`budget_evidence_complete` requires all 18 receipts plus known usage/spend for
each; complete evidence can still show overruns. `budget_compliant` is false for
any known violation, true only for complete reported data within limits, and null
otherwise. Neither field means execution is authorized. Runtime stopping/enforcement is not
implemented, and future timeout/overrun-handling policy still needs review.

## Existing offline resource envelope and review gate

Use only standard-library synthetic fixtures, one sequential CPU worker, no
bytecode writes, and 60-second shell caps per focused/full test or audit command.
Existing tiny oracle bounds remain unchanged; neither exports nor package files
are regenerated. The historical 122-test result is a prior receipt, not a new
run. New counts must be recorded separately after execution.

Next decisions: accept corpus/arithmetic and permitted use; decide oracle-only
policy; agree solver/proof interfaces; review actual shared/output prompts,
provider/model revisions, token/wall/spending limits, four-call proposal,
termination/retry/usage accounting and run order; grant separate execution
approval if appropriate. Do not infer any of those from passing offline tests.
