# Offline Tier A contract proposal v1

This standalone software proposal is not team acceptance of a research protocol,
corpus use or model run. It has no runner, CLI, provider, translated-instance tool,
network call or output writer. Import `tier_a_contract` from the repository root.
It is outside the hashed `surgerybench` package and is not included by its existing
wheel configuration. Existing sources and all four Tier A exports are immutable.

`evaluate(directory, plan, receipts)` reuses the full existing Tier A auditor and
then pins all four reviewed export SHA-256 values, not only their self-reported
manifest. It returns scores only after preflight and routing validation succeed.
`model_inputs(directory, plan)` performs the same preflight and returns nine text
strings only, in corpus order: no case IDs, family/tags, gold or arithmetic. This
is an API boundary, not process isolation against code already holding gold. A
future approved runner must supply these identical strings to both arms; this
module constructs no prompts and invokes neither provider nor solver.

## Explicit plan and receipts

Plan keys are exactly `contract_version`, `corpus_version`, `case_use`,
`repetitions`, `arms`. Versions are `tier-a-offline-contract-proposal-v1` and
`tier-a-original-synthetic-v1`. Arms must be `['no_tools','csp']`; caller supplies
an integer repetition count 1..10 (software cap, not a selected research R).
`case_use` must map every one of the 15 IDs: the six `oracle_only` negatives to
`validation_only`, the remaining nine to `eligible`. No case may be dropped or
silently added. No accepted-protocol flag or automatic approval manifest exists.

Receipts are a list with exact keys `case_id`, `repetition`, `arm`, `raw_output`,
`normalized_output`, `normalization_errors`, `provider_error`, `tool_error`,
`termination`. Repetition is a zero-based integer (not boolean). Unknown/excluded
IDs, unplanned arms/repetitions, duplicates/retries and invalid metadata reject
the entire request, not individual rows removed from denominators.

`raw_output` is JSON text up to 64 KiB, or null when unavailable. The caller
retains `normalized_output`; this module never repairs it. Parsing rejects
duplicate keys and nonfinite constants. Canonical raw/normalized comparison must
match without numeric/string/boolean coercion. Normalization diagnostics must be
a list of nonempty strings, and any diagnostic prevents evidence credit. Raw,
normalized and diagnostics remain in each returned receipt. Malformed output
remains an attempted row with output error; normalization cannot rescue it.

`provider_error` and `tool_error` are booleans and may overlap. Termination is
`final`, `abstained`, `provider_error` or `tool_error`; operational termination
requires its matching flag. Timeouts use the corresponding operational flag and
termination plus an explicit diagnostic such as `provider timeout`. No timings,
token usage, pricing, real model/adapter revisions or costs are invented here.
Those belong to a separately frozen future execution receipt contract.

## Frozen output shapes

- FEASIBLE: exactly `status` and non-null `schedule` list. Existing checker
  validates each row and all intended-instance constraints. Any valid witness,
  including non-gold schedules and optional omission/inclusion, can succeed.
- INFEASIBLE: exactly `status` and non-null `certificate` object, accepted only
  by the existing intended-instance pair-order checker. A different valid pair
  ordering is allowed. Unsupported/false/null proofs give no certified success.
- UNKNOWN: exactly `status`; no reason/schedule/certificate keys, even null.
- Other objects/scalars, extra keys, missing evidence or null fields are output
  errors. Bare INFEASIBLE retains diagnostic negative decision agreement only.
  That diagnostic also survives invalid proof/extra evidence keys when a parsed
  matching raw status is available; it never earns evidence-backed success.
- Explicit metadata abstention requires raw/normalized null, empty normalization
  diagnostics and no operational flags. It counts UNKNOWN and completed, with a
  separate diagnostic. Null final output instead counts an output error.

Operational flags or non-completion always block evidence success, even with a
valid schedule/certificate. No solver-native status is promoted to certification.

## Planned denominators and pairs

Every arm has exactly 9R planned slots: 7R feasible and 2R supported negatives.
All six oracle-only negatives are excluded from every model denominator and any
attempt routed to them rejects the request. Every slot is retained: UNKNOWN,
output errors, operational failures and missing receipts never shrink a metric.
Metrics expose integer numerator/denominator counts. Negative decision agreement
is diagnostic; certified success requires valid intended-instance evidence.
Failure flags may overlap. Missing is separate from output/provider/tool error.

Attempted means a receipt exists. Completed means `final` or `abstained` (including
invalid final outputs); operational termination is attempted but not completed.
Summaries are incomplete when any planned slot is not completed. Pair buckets are
both-success, no-tools-only, CSP-only, neither-success and incomplete. A pair is
incomplete if either arm lacks completion; no complete-case-only primary metric
or attempted-only comparison is emitted. Eight represented families get separate
planned-denominator summaries, not independence/significance claims or a macro
optimization score. Source and consumer hashes accompany results.

Run bounded tests from the repository root with standard-library Python:

    timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
    timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s tests -q

Tests use only synthetic recorded attempts and copied packages for corruption
checks. No corpus regeneration is necessary. Team arithmetic/corpus acceptance,
solver/proof interface, prompting/budgets/retry protocol, receipt/timing/usage
design and separate execution approval remain open. No model run follows from
passing these software tests.
