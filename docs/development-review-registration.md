# Development review metadata and offline registration preparation

Baseline 3f20017148b3290c518483b60afc7c4a75971a9e; all work on xlogin. Existing
corpora, generators, scorers, prompts and earlier review artifacts remain immutable.
This increment adds review descriptors/diagnostics and an offline consumer draft,
not a live runner, provider, protocol acceptance or new holdout split.

## Finer lineage, keeping a conservative parent

`development_lineage` records 240 v2, 96 v1 and 63 original pilot/Tier A instances.
Namespaced keys prevent conflating IDs across packages. Generator/source version,
source hash, seed, suite, ordinal and settings identity are retained where present;
legacy rows without producer ordinals use explicit null plus physical ledger index.
Known analytical references are AST-checked and labeled direct generator, exact
analytical match where previously established, or shared construction motif. No
new historical parent direction is inferred from matching content.

Four deterministic descriptor levels:
- exact: canonical original instance, including IDs/metadata/numeric values;
- normalized: ordered job/resource renaming, sorted eligible-room indices, remove
  priority/emergency metadata; when exactly one active day, shift all job/calendar
  times by minimum release and collapse that active day/budget to day0;
- topology: patient/resource counts, fixed surgeon graph, eligible-room graph and
  mandatory mask, retaining list order;
- mechanism: topology plus resource window-count pattern and positive-gap flags.

No exhaustive graph isomorphism, arbitrary permutation search, unit scaling or
unrestricted semantic equivalence is claimed. Unused resources remain significant.
Mechanism groups collect numeric variants for REVIEW, not independent sampling.
All records keep parent `related-development-pilot-tier-a-and-derived-suites`.
Zero cross-population matches cannot establish independence or new construction.

Results: 399 exact and 399 normalized groups; 108 topology and 177 mechanism groups.
V1/v2 share 519 topology pairs (73 v1 cases,72 v2 cases), 360 mechanism pairs (54/44).
No exact or normalized cross-population matches; no original63-to-generated topology
matches under this count/order-sensitive definition. Original/test motif relationships
remain linked despite no descriptor equality. All known sources stay development.
Ninety-eight child/parent edges record90 relaxed variants plus8 mandatory-counterpart
controls with source case, relation, child instance/topology hashes. They are not98
additional accepted corpus cases. Source manifests and descriptor implementation hash
are retained in the new ledger; older coarse exports are not rewritten.

## Selected interactions and optional semantics

`development_counterfactuals_v2` adds room_gap+surgeon_gap, low_budget_proxy+room_gap
and surgeon_gap+flexible to the prior room_gap+fragmented and low_budget_proxy+flexible.
Each relaxation independently changes only named constraints: zero corresponding gaps,
merge windows within original outer extent, raise room budgets without decreasing them,
or expand eligibility to all existing rooms. Resource identities/surgeons/mandatory
flags stay fixed. The whole Boolean lattice is checked: original->A/B/both and A/B->both.
A known FEASIBLE->INFEASIBLE edge rejects; UNKNOWN leaves that edge unresolved.

Selection: first two structurally eligible ordinals per profile/cell, including
quarantined cases, never selecting by label change. Thirty four-way cases/120 variants
completed with no UNKNOWN: one I/I/I/F joint contrast, one I/I/F/F calendar effect,
28 no label changes. The three new pair types showed no label change in 18 selected
cases. This is useful bounded negative evidence, not absence of effects generally.
Six profile/cell selections were short: four no-flexibility cells in one-room
profiles and two low-budget/room-gap cells with only one eligible ordinal. Ten other
pair types remain structural-only; no comprehensive interaction coverage claim.

Eight separate optional controls compare original omission-permitting semantics to
all-optional-made-mandatory counterparts. Two original FEASIBLE cases become INFEASIBLE,
six do not change. This demonstrates optional omission, NOT optional binding in the
original hard-feasibility task. There is no soft objective. All counterfactuals are
validation-only oracle diagnostics; none bypass actual-tool admission into model cases.
Domain product>100 or incomplete oracle returns UNKNOWN. Feasible witnesses are checked.

Within v2 alone: 82 topology groups, 128 mechanism groups; 30 mechanism groups contain
multiple numeric variants, largest 25. Settings identity hashes normalized JSON via
json.dumps(settings,sort_keys=True) with its default separators; source manifests
retain exact file hashes separately. No numeric-variant family is promoted to holdout.

## Explicit offline consumer registration

`development_registration.preflight` accepts only seeded-development-suites-v2 with
an explicit plan: registration_version, corpus_version, input_view_version,
manifest_sha256, consumer_sha256, instruction_sha256, planned_case_ids, arms and
repetitions. Both arms are fixed no_tools/csp; repetitions1..10 is a software bound,
not a team-selected research setting. Selection/order is explicit before receipts;
only already accepted evidence-eligible IDs are legal. Quarantined/old/mixed/tampered
or unsupported data fail closed. This is a new draft entrypoint, not a change or
silent registration in old hash-pinned Tier A preflight.

New bounded snapshot reader: opens a directory fd with no-follow, scans at most 6
entries; each exact-name file must be non-symlink regular and <=2MiB by fstat BEFORE
reading. Reads remain capped if a file grows; UTF-8 JSON depth<=64 and JSONL rows<=128
are checked before parsing. Files are copied as bounded bytes into a private temporary
snapshot, then the unchanged old v2 auditor checks that snapshot. No hostile path
reopen race into the original data is needed. Existing standalone auditor remains
unchanged for historical version identity; new consumers must use this bounded
entrypoint. Declared source files on disk are still trusted protected checkout
inputs; this is not authenticated history of actual tool calls or all dependencies.

`model_inputs` returns ONLY shared instruction, arm instruction and already-derived
v2 text in planned order. IDs/labels/families/lineage/selection/receipts/hashes remain
in separate plan/slot/evaluator metadata. Necessary surgery/resource IDs are task
content. The shared text is equal across arms; actual provider message roles and CSP
exposure are not implemented. A fingerprint alone never admits a package: plan hash,
version, source identities, full audit and accepted membership must all pass.

`assess` is a small offline recorded-evidence preview reusing frozen output_verdict.
It consumes the existing underlying receipt fields, rejects duplicate/unplanned
attempts and retains every explicit case/repetition/arm slot. UNKNOWN/abstention,
errors/timeouts and missing receipts cannot shrink planned denominators or become
success without intended-instance evidence and error-free final termination. It adds
no completion, budget, latency/token, retry or research protocol definition. General
issue9 execution/aggregation work is not taken over. PR20 execution/completion wrappers
remain a separate proposal, not activated here; underlying receipt shapes are compatible.

Concrete QA plan selects first 3 accepted reference records, no label-based selection,
R=1 purely for software QA: 3 inputs per arm, 6 planned slots. Empty receipts report
3 missing/0 successes per arm; this is not an experimental result or run authorization.
The plan hashes consumer and shared/arm instructions. No provider or model is invoked.

## Verification and remaining decisions

Focused tests cover descriptor determinism and invariances, full-lattice violations,
optional counterpart semantics, pre-read/pre-parse caps, explicit plan identities,
old/new cross-feed, matched payloads, and fixed failure/missing denominators. Full 162
normal/optimized tests passed with recorded exit 0. All prior bytes are preserved.
The corpus stays at 240 candidates/200 accepted/40 quarantined: this increment adds
review evidence, not accepted cases. More detailed mechanism hypotheses, unbiased
interaction selection and broader graphs remain research work, not done by hashes.
Before real use, team must accept corpus/selection and input/message/tool contract,
choose provider/budgets/prompts/repeats and explicitly approve execution. No new user
choice is needed merely to continue already-approved offline dataset development.
