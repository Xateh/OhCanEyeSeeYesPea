# Development suites v2: hardening, breadth and selected ablations

Baseline 3f20017148b3290c518483b60afc7c4a75971a9e; local xlogin only.
Original v1 generator,96-case exports and receipts remain unchanged. New version
seeded-development-suites-v2 has separate outputs/source identities. No GitHub,
credential, provider, install, commit or publication action in this slice.

## Admission and replay

Settings use existing strict JSON: duplicate keys/non-finite constants reject.
Expose duration_min/max, slack_max, gap_max, budget_min, optional_percent plus prior
seed/counts/horizon/suites/caps. Booleans reject as integers. Counts1..16 are this
implementation profile, not schema/user authorization limits. One day,<=2 windows,
mandatory product<=100, oracle limit<=10000, patient*room*1440<=100000,<=128 candidates
per build,40-second internal wall budget and60-second shell caps. Stable suite/ordinal
and seeded instances; no replacement sampling after rejection. Separate RNG streams
are not statistically independent cases. Construction lineage remains related.

Timeout retains examined receipts plus explicit unexamined ordinals. Manifest/coverage
status incomplete; model/gold exports empty; diagnostics retain ALL receipts, including
examined accepted outcomes. Ordinary audit rejects incomplete output. A process kill
or disk failure can leave an incomplete new directory; exact files/hashes reject it.
Never overwrite output. No partial accepted corpus presented as complete.

`development_suites_audit.audit` checks exact files/manifest/receipt schema, version,
source/file identities, settings, seeded canonical instances/ordinals/IDs; recomputes
bounded oracle labels/receipts; checks gold/tool evidence, raw/derived text, joins,
quarantine separation and accounting. It does not rerun CSP: stored tool evidence is
checked against intended instances and pinned producer source, not independently
authenticated proof of historical execution. Hashes are not authorship/human acceptance.
Auditor reuses candidate() for provenance replay, not a second generator/oracle.
Old Tier A contract/scorer remains unchanged and rejects this unregistered format.

Original v1 FULL96 replay matched all5 files byte-for-byte; v2 FULL96 replay matched
all6 files including receipts.jsonl. Performance stays outside deterministic identities.
Original v1 had72 accepted; v2 has74 under explicitly changed version/RNG/ranges, not
retrospective replacement of old results.

## Achieved profiles (patients/surgeons/rooms)

| Profile | Counts | Candidates | Accepted F/I | Quarantined | Rejected |
| --- | --- | ---: | --- | ---: | ---: |
| reference | 3/2/2 | 96 | 44/30 | 22 | 0 |
| surgeon_scarce | 4/1/1 | 48 | 11/35 | 2 | 0 |
| room_scarce | 5/3/1 | 48 | 11/28 | 9 | 0 |
| room_flexible | 2/2/3 | 48 | 39/2 | 7 | 0 |
| Total | four configurations | 240 | 105/95 | 40 | 0 |

All24 profile/suite cells exercised. All240 structures exactly unique, not normalized-
isomorphism deduplicated or independent. All200 accepted evidence-eligible;40 complete-
oracle negatives are validation-only QUARANTINED for tool UNKNOWN. Accepted validation-
only count0. Later evaluated UNKNOWN/timeouts remain in frozen planned denominators.
Actual canonical-groundtruth tool: CSPAdapter.invoke / temporal-minute-dfs-v1,
100000 nodes/2seconds, independent oracle and intended checker. No new OR-Tools claim.

Numeric profiles: surgeon_scarce duration1..2/slack0; room_scarce1..2/slack0..1;
room_flexible duration2..3/slack0..2/gap0..2/budget>=2/optional60%. Seeds/source/settings
retained. New48-case build PLUS audit elapsed wall times:0.181s/0.239s/0.190s,
not CPU or model timings. Structural flags are presence proxies, not binding proof.
Rename budget_bottleneck to low_budget_proxy (room budget below total mandatory
duration regardless of allocation). Reference/flexible profiles show all15 pairs;
surgeon_scarce misses5 flexible pairs; room_scarce misses those5 plus fragmented+
low_budget_proxy and low_budget_proxy with optional/room_gap/surgeon_gap. Exact counts
are in summary JSON. No exhaustive factor/value coverage claim.

## Selected measured effects (validation diagnostics only)

Two selected cells: room_gap+fragmented, A=zero room gaps, B=merge resource windows
within existing min/max spans. low_budget_proxy+flexible, A=raise room budgets to
nonbinding calendar-end upper bounds without decreasing existing budgets, B=allow
all existing rooms. No surgeon reassignment or mandatory-flag change. Schema check,
product cap100 (otherwise UNKNOWN), complete oracle limit10000 and feasible-witness
checker for every variant. No new negative proof or accepted model example created.

Selection: first2 structurally eligible candidate ordinals per profile/cell, including
quarantine; not selected by label. Twelve cases/48 variants, all complete. One
room_scarce case18993da0eb2be386f70a697e had I/I/I/F for original/relaxA/relaxB/both:
both relaxations jointly needed in this specific contrast. One room_flexible case
fe3f06a36d2c9aeb5886e45e had I/I/F/F: window relaxation alone restores feasibility;
no evidence that gap was binding. Other10 selected cases had no label change.
Four low-budget/flexible cases show no label effect, not proof budget never binds.
One-room profiles have no flexible cases, leaving two selection cells empty.
Thirteen other flag-pair cells remain structural-only. No general causal/statistical
interaction claim follows. Unit tests additionally verify a known joint gap/window
construction and eligibility relaxation returning UNKNOWN at the product cap.

## Artifacts and limits

Under /home/t/tehxa/cs3263-review/: seeded-development-v2-96-20261105,
seeded-development-v2-96-replay-20261105, v2-{surgeon_scarce,room_scarce,room_flexible}-20261105,
breadth-hardening-summary-20261105.json, development-counterfactual-review-20261105.json.
Replay directories are evidence copies, not extra testcase counts. Future work:
more predeclared ablations/levels, finer cross-source structural lineage, profile/value
coverage and explicit package-consumer registration. These are development_review
outputs, not holdouts or human/team acceptance. No new user choice needed for
quarantine or already-approved seeded/count/interaction direction.
