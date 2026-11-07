# Seeded configurable development suites (design, not implemented)

User choices: BOTH constraint interactions and numeric diversity; configurable
scarcity/counts, seeded reproducibility, presets, dynamic canonical-CSP and actual
tool validation. Fresh teammate reconciliation precedes generator implementation.
Last fetched main3f20017148b3290c518483b60afc7c4a75971a9e; PR20 branch25e1bde419be82e69c576de823d391e9091cc00a.
Latest read lacked cached credentials. No auth/GitHub action during this design.
Everything here is development-visible, not final held-out cases.

## Proposed interface/settings

Future build_candidates(settings) -> ordered records; validate_candidate(canonical,
claim, adapter, limits) -> admission/evidence receipt; export_validated(records,
new_destination, version) -> separate model/gold/coverage/manifest. No overwrite,
provider or experiment runner. Reuse latest teammate interfaces, not these names
as an imposed team API or competing solver ownership.

Settings: format_version, suite, seed, candidate_limit, accepted_limit,
max_rejections, patient_count, surgeon_count, room_count, days, horizon_minutes,
duration_range, release_window_range, deadline_slack_range, mandatory_fraction,
room_eligibility_density, calendar_windows_per_day, calendar_fragmentation,
room_gap_range, surgeon_gap_range, room_budget_range, surgeon_budget_range,
interaction_factors, numeric_variants_per_construction, required_coverage_cells,
oracle_product_cap, oracle_assignment_limit, solver_node_limit, solver_seconds_limit.

Counts determine scarcity ratios, not redundant conflicting ratio fields. Reject
unknown settings, zero counts, invalid ranges/fractions, unsupported envelopes or
product overflow before search. Pin RNG algorithm/Python/generator revision, seed,
draw/enumeration order and every candidate/rejection ordinal; seed alone is not
sufficient reproducibility. No selection based on evaluated-model performance.

The initial smoke profile may reuse the tiny Tier A settings: at most two patients,
rooms and surgeons, one day, endpoints/durations/gaps/budgets at most 10, at most
two windows per resource/day and domain product at most 100. These are frozen Tier A
builder/auditor limits, NOT general tool/schema limits or user-authorization limits.
Fetched surgerybench/temporal_check.py:schema_errors delegates structural checks to
surgerybench/checker.py:schema_errors, which permits 1..56 days and has no explicit
patient/surgeon/room count ceiling of two. surgerybench/temporal_oracle.py:
enumerate_schedules and surgerybench/temporal_csp.py:solve likewise have no such
count ceiling; the oracle caps combinations and DFS caps nodes/time.

The configurable DESIGN therefore covers larger count/scarcity configurations,
subject to schema validation and explicit fail-closed workload bounds. Preserve the
bounded sequential CPU envelope: one worker, 60-second command caps, oracle assignment
limit 10,000 and declared finite domain-product/search limits. The initial conservative
domain-product cap can remain 100 without imposing a two-patient restriction.
Bound input sizes, resource/calendar scans, mandatory-job/day/eligible-room minute-domain
construction, pair checks and optional-job processing as well as the Cartesian product:
a small product alone does not bound preprocessing or large optional populations.
Validate settings and reject workloads exceeding declared bounds before search;
retain node/time-limit outcomes as UNKNOWN. Schema acceptance is not a performance
guarantee. Final supported bounds and actual adapter capabilities must be reconciled
with latest Allan code after access returns. No wider generation executes in this
documentation slice. More parallelism, longer commands, new allocations or installs
remain outside this envelope; larger counts alone are not a new approval requirement.

Presets: scarcity_contention; fragmented_gap; eligibility_budget; optional_load;
combined_constraints (predeclared interaction cells); parameter_sweep (seeded values
within reviewed mechanisms). Malformed_input is separate, validation-only and opt-in,
never ordinary model input. Pair/covering-array coverage is a design target, not
an exhaustive Cartesian claim. Report achieved/missing cells and failures; numeric
variants retain common construction groups, not IID sample claims. Suite counts
are bounded settings/admission choices, not a new budget or run commitment.

## Dynamic groundtruth/actual-tool flow

1. Build canonical schema1.1 CSP instance, keeping authored intent separate from
   verified label. Record primitives, generator provenance and construction group.
2. Validate schema/envelope and independent domain-product bound before search.
   Render NEW version text without fixed-ID examples; parse back and compare fields.
3. Complete bounded independent Cartesian enumeration supplies internal groundtruth.
   Feasible witness must pass unchanged intended-instance checker. UNKNOWN/incomplete
   never becomes negative. Independent arithmetic remains a separate review gate.
4. Invoke ACTUAL approved CSP adapter on canonical structure in an offline validation
   lane. Keep arguments, adapter revision, status, nodes/time/errors and evidence.
   This is CSP-on-gold validation, not the evaluated model-to-CSP arm. Externally
   check tool schedules/certificates on intended instance; quarantine contradictions.
   Unsupported conditions, errors/timeouts remain UNKNOWN in tool receipts.
5. Admission: feasible+valid witness can be evidence-eligible after required gates;
   negative+exact frozen pair_order_impossible proof can be eligible. Complete-oracle
   negatives lacking supported proof remain validation-only. Tool UNKNOWN may coexist
   with independently proven gold, but does not itself prove negative or complete
   the actual-tool validation gate. Required unresolved gates block accepted export.
6. Retain all candidates/rejections/UNKNOWN receipts. Freeze eligible case-use before
   future runs; never drop failed attempts or retroactively shrink planned denominators.
   Keep separate validation-only counts and groundtruth-vs-translated-tool receipts.

Fetched interface: surgerybench.temporal_csp.CSPAdapter.invoke requires exactly
{'instance': schema1.1_object}. solve returns FEASIBLE+schedule, supported
INFEASIBLE+certificate, or UNKNOWN (search_limit or exhausted_without_supported_certificate).
It is stdlib DFS, NOT verified Allan OR-Tools integration. Reuse rather than rebuild.
Missing evidence: latest published Allan branches/testcases; actual adapter entrypoint,
supported schema/constraints/status/proof/limit/version mapping. Inspect them before
coding a generator/validation integration. No guessed interface or installation.

Gold is evaluator-side. Ordinary models get standardized text/common instructions;
CSP gets MODEL-translated arguments, never injected canonical groundtruth. Dynamic
groundtruth validation and evaluated translated-CSP behavior are distinct lanes.

## Preservation and remaining decisions

New generator/corpus/text versions require separate exports and explicit registration.
Current hash-pinned old auditor/scorer/input helper must reject new unregistered
corpora; never weaken old preflight. Reuse primitive checkers/oracle and actual team
adapter, preserving original15/48 and all previous reviewed bytes. Expansion remains
development/validation with honest construction grouping, not independent holdout.

Already decided: interactions AND numeric diversity; seeded settings/scarcity/presets;
dynamic canonical/actual-tool validation; no misleading absent-ID examples in ordinary
inputs. Do not ask again. After reconciliation, resolve authoritative adapter/version
with its owner from actual published evidence. Under the already-authorized dynamic
actual-tool validation requirement, unresolved required tool validation quarantines
candidates before accepted export, even when an independent oracle has verified gold.
Keep those receipts as diagnostics; no additional approval is required for this
conservative admission rule. This pre-export quarantine does NOT remove subsequent
UNKNOWN, timeout or error attempts on accepted, planned evaluation cases from frozen
evaluation denominators. Request a larger resource envelope only for genuinely larger
compute requirements, not merely a larger configured patient count. Prompt
adoption, tool exposure/output interface and experiment budget/protocol remain team
choices; general issue9 configuration/aggregation is not added here.
