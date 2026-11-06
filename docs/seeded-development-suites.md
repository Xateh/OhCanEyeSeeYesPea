# Seeded development suites v1: local prototype

Fresh published refs checked on xlogin,5November2026: main3f20017148b3290c518483b60afc7c4a75971a9e;
PR20 head25e1bde419be82e69c576de823d391e9091cc00a. All advertised branch/PR-head
refs fetched to team-review/team-pr namespaces, preserving original origin/HEAD.
No Allan-authored non-merge commit appears in those reachable histories. Allan Robert
merged PR1/15/16/17/18 on30October; that is merge activity, not new testcase/solver
implementation evidence. Benjamin/Benjumpin authored the published scoring-freeze
commits79a27e9 and dd85bdb on31October (README.md/docs/evaluation-framework.md).
Git refs/logs do not establish current PR comments/open/draft status or unpublished work.
No published OR-Tools adapter was found; use existing temporal_csp.CSPAdapter.invoke.

## Implementation and limits

`development_suites.py` builds separate original-synthetic development candidates.
Required settings are exact keys from DEFAULT, with seed, patient/surgeon/room counts,
horizon, suite order, candidates per suite and preprocessing/product/oracle caps.
Counts1..16 are this prototype's explicit fail-closed implementation profile, NOT a
schema/tool limit or a user-authorization limit. Counts determine scarcity. The
profile has one day, horizon1..10, integer durations1..3 (bounded by horizon),
release/deadline slack0..1, up to2 eligible rooms and2 resource windows, gaps0..1,
budgets1..horizon where varied, optional inclusion probability.65 (first mandatory).
These ranges are preset semantics, not all individually configurable yet. Unsupported
settings fail rather than being ignored. Do not claim the full earlier design is built.

Six presets combine scarcity, fragmentation/gaps, eligibility/budgets, optional load,
combined constraints and numeric-only baseline. Per-candidate RNG uses SHA256 of
version/seed/suite/ordinal; record Python/generator versions and exact source hashes.
Rejections never trigger replacement draws. Same settings/source reproduce exact
export bytes; existing destinations are refused. A write failure can leave a partial
NEW directory, never treated as verified output. No retry-overwrite/resume behavior.

Before oracle/tool calls: settings/count/schema checks; patient*room*1440<=100000;
finite mandatory-domain product<=100; oracle limit<=10000; at most128 candidates.
Counts/window limits also bound optional processing/resource scans/pair checks.
Actual existing adapter invoked with canonical schema1.1 groundtruth, using unchanged
solver default100000 nodes/2seconds per call. Build stops before export if elapsed
budget40seconds is exceeded between candidates; external60-second cap remains required.
No installs, parallelism, extra allocation, providers or evaluated models.

## Evidence and separation

Independent existing Cartesian oracle determines internal label only when complete;
all oracle witnesses pass intended-instance checker. Actual CSPAdapter receives a
copy of the canonical instance; tool witness/certificate is independently checked.
Only agreement with valid required evidence is accepted. UNKNOWN/error/contradiction
is quarantined; complete-oracle negatives without frozen pair proof are validation-only,
not silently promoted. Groundtruth CSP-on-gold validation is separate from any later
MODEL-translated CSP lane. Later evaluation UNKNOWN/timeouts stay in planned denominators.
No scorer/contract was changed. This package is NOT registered for either old harness
or old Tier A contract; new version-specific consumer/auditor integration is still needed.

model.jsonl has case_id/text only; case_id stays runner-side, prompt sees only text.
Gold retains canonical instance/witness/proof/oracle/tool receipts, never prompt input.
Diagnostics retain rejected/quarantined records separately. Coverage and manifest are
privileged evaluator metadata. The v2 exact text view removes fixed A/E example without
supplying any actual pair. Original48/TierA15/text/scorer files remain untouched.

All records are related development material, including to prior pilot/analytical
sources. No independence/holdout/novelty/clinical/model-performance claim. Structural
flags and pair co-occurrence counts are NOT proofs of binding constraints or difficulty.
`budget_bottleneck` is a proxy (room budget below total mandatory duration), not a
proof that eligible assigned load must exceed that budget. Numeric variants are not IID.

## Local96-candidate build

Settings outside checkout: /home/t/tehxa/cs3263-review/seeded-development-20261105-settings.json.
Output: /home/t/tehxa/cs3263-review/seeded-development-20261105.
Seed326305;16 candidates per each of6 suites;3 patients,2 surgeons,2 rooms,horizon8.
Accepted72:44 feasible/28 independently pair-certified negative. Quarantined24:
complete-oracle negative, validation-only, actual tool UNKNOWN; no accepted validation-only
cases. No bounds/schema rejection in this build. All15 pairs among6 structural flags
have accepted co-occurrence; exhaustive factor/value coverage is NOT claimed. Source
code, settings, manifest and coverage bind this run; do not silently expand/relabel it.

Publication, real model runs and spending are not authorized. Actual-tool validation
is fulfilled here by the current published stdlib adapter, not a claimed Allan OR-Tools
interface. Later published adapter integration should reuse this evidence boundary,
not duplicate or silently substitute the solver. Broader parameter controls and
larger profile support can be implemented against actual requirements and measured
bounds; no need to re-ask already approved seeded/interactions/scarcity direction.
