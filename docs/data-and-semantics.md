# Dataset and scheduling semantics

## Published pilot versus historical corpus

This checkout contains **48 original synthetic cases**, 24 paired families and four overlapping themes: tight windows, room contention, fixed-surgeon contention and eligible-room bottlenecks. Every family contains a feasible instance and a counterfactual changing only surgery E's completion deadline by minus one minute. There are 2–3 mandatory surgeries per case, all resource gaps are zero, and each resource/day has at most one availability window; no paraphrase multiplication. Positive gaps, optional jobs and broader calendars are schema capabilities with focused tests, not coverage established by the shipped corpus.

The separate historical 1,440-case corpus (540 source-derived plus 900 original synthetic) is **not included**. Its receipts and labels must not be mixed with this pilot. Source redistribution permission remains unresolved; [PROVENANCE.md](../PROVENANCE.md) is the inclusion boundary.

| Split | Families | Feasible | Infeasible | Cases |
|---|---:|---:|---:|---:|
| Train | 16 | 16 | 16 | 32 |
| Validation | 4 | 4 | 4 | 8 |
| Test | 4 | 4 | 4 | 8 |

For each theme, family indices 0–3 train, 4 validation, 5 test. Durations increase with index. Family separation prevents pair leakage across splits but does not imply IID sampling, statistical independence or broad difficulty.

## Files and provenance

- `model.jsonl`: exactly `id` and `text` per row. This alone is passed to the provider.
- `gold.jsonl`: aligned IDs plus intended instance, label, witness/certificate, hashes, lineage, family/theme/split and oracle counts. Keep out of model context.
- `summary.json`: counts, generator and explicit limitations.
- `manifest.json`: SHA-256 of the other three files; expected bytes are checked by the package tests.

`temporal_dataset.build(new_directory)` refuses existing directories. Seeds are deterministic per family. Two builds under identical package/Python identity reproduce bytes. When comparing packaged regeneration to older original fixtures, verification ignores only `id`, `lineage.code_revision` and `lineage.python`; text, semantics, evidence, families, seeds and splits must match. The original provenance is not rewritten to claim a newer generator made those bytes.

```bash
python3 -m surgerybench.temporal_dataset fixtures/arrival-deadline-v1 --audit
python3 -m surgerybench.temporal_dataset runs/new-pilot
```

The second command requires a nonexistent destination; use a new name each time.

## Schema 1.1

Top-level fields: `schema_version: "1.1"`, `days` (integer 1–56), `day_minutes: 1440`, `surgeons`, `rooms`, `patients`.

A resource has:
- `id`: identifier beginning with a letter, then letters/digits/underscores; unique within its resource kind
- `gap`: nonnegative integer separation between its surgeries
- `budgets`: one integer surgery-minute limit (0–1440) per day
- `calendar`: one list of sorted nonoverlapping `[start,end]` windows per day, with integer `0 <= start < end <= 1440`

A patient/surgery has `id`, boolean `mandatory`, fixed existing `surgeon`, integer `duration` (1–1440), integer absolute-minute `release` and `due`, unique existing `eligible_rooms`, nonnegative integer `priority`, and optional boolean `emergency`. Temporal bounds require `0 <= release <= due <= days*1440`. Python booleans are rejected where integers are required.

For new registrations explicitly selecting `temporal_validation_v2` (`temporal-strict-validation-v2`), the top-level `surgeons`, `rooms` and `patients` containers must be JSON arrays. Resources and patients must be JSON objects with exactly the documented fields (only patient `emergency` is optional). Budgets, calendars, each calendar day, eligibility and each two-element calendar window must be arrays. Unknown or misspelled fields fail closed instead of silently dropping an unsupported constraint. Empty top-level arrays and empty day-window arrays remain structurally valid; existing reference, horizon and mandatory-scheduling checks still apply.

`temporal_validation_v2.normalize_instance` returns a validated deep copy and supplies only an omitted `emergency: false`. Rendering uses this normalization without mutating the caller. Thus `parse(render(instance)) == normalize_instance(instance)`; exact equality to a non-normalized instance is not promised. Existing explicitly populated instances retain the same text bytes. Priority/emergency remain metadata with no scheduling effect. No unknown field or scheduling constraint is normalized away.

Schedule rows must contain **exactly** `patient`, `day`, `start`, `room`; day is zero-based and start is an integer minute after midnight. The surgeon and end are derived from the instance, never reassigned by output.

## Hard constraints

For a row with surgery duration d:
- Absolute start = `day*1440 + start`; start >= release; completion = absolute start + d <= due.
- Each mandatory surgery occurs exactly once. Optional surgeries may be omitted, otherwise at most once.
- The surgery occupies one uninterrupted half-open interval `[start,start+d)` in an eligible room and with its fixed surgeon.
- The entire interval fits one availability window for **both** resources. No crossing breaks or splitting.
- No room or surgeon overlap within each day; previous end + resource gap <= next start. Gap checks are per resource/day, not across day boundaries.
- Sum of surgery durations per resource/day <= its daily budget. Gaps are separation constraints, not additional surgery minutes.
- Priority and emergency flags are metadata only: no preemption, priority objective or unstated clinical constraint.

Schema 1.0 uses inclusive **day** release/due bounds. `temporal_check.relaxed()` changes them in a deep copy to reuse legacy resource validation, then applies schema-1.1 temporal bounds separately. Never reinterpret a 1.0 input as 1.1 without explicit conversion.

## Status and proof

- FEASIBLE needs a schedule independently accepted by `temporal_check.check_schedule`.
- INFEASIBLE certification supports only `{"kind":"pair_order_impossible","patients":["A","E"]}` (IDs vary). Both jobs must be mandatory and forced to share the fixed surgeon or the same singleton eligible room. Neither ordering can satisfy arrivals/completion deadlines even after relaxing calendars, budgets and gaps. This necessary-condition contradiction proves infeasibility.
- UNKNOWN means no supported answer established. Time/node/combination limits never justify INFEASIBLE.

The standalone Cartesian oracle enumerates complete assignments for tiny valid instances independently of generator/CSP/checkers. DFS may exhaust its search yet return UNKNOWN if it has no supported compact certificate. Certificate kinds in the legacy schema-1.0 checker are not accepted by the temporal checker.

### Boundary example

One room available [0,10), distinct surgeons, A arriving 0 with duration 4/deadline 10, E arriving 3 with duration 4/deadline 8: the unique schedule is A [0,4), E [4,8). Tightening E's deadline to 7 makes this infeasible despite only 8 total surgery minutes. Splitting A into [0,3) and [7,8) is invalid.

## Before expanding the dataset

Agree target scale, constraint coverage, difficult/ambiguous language cases and difficulty evidence; keep development/test families separated and audit transformations. Clinical realism, unrestricted language understanding, broad optional-surgery optimization and statistical generalization have not been established. Any adaptation must preserve traceable source/synthetic fields and independently validate new labels; published original-problem scores are not optimal scores for a changed problem.

## Offline boundary follow-up (local, 7 November 2026)

`tests/test_temporal_boundaries.py` checks schema/text/parser/checker boundaries, absolute minutes 1439/1440, exact horizon completion, whole-surgery midnight rejection, per-day budget/gap rules, empty/all-optional workloads, resource/job/identifier/metadata invariance and intended-instance scoring. Its tiny exhaustive-oracle checks are offline software regressions, not new corpus admissions or model experiments. Historical datasets, texts and results are preserved.

Four oracle-proven infeasible constructions (deadline, calendar, budget and gap) deliberately lack a supported pair certificate. They remain a separate validation stratum with expected solver UNKNOWN: 4 planned, 4 oracle INFEASIBLE, 4 solver UNKNOWN, 0 certified successes. A search-exhaustion diagnostic does not become a supported final certificate, and these cases must not disappear from denominators.

Optimality is not implemented. The current prompt defines no optimization objective, priority/emergency are metadata, optional surgery may be omitted, and the tiny oracle enumerates mandatory-only feasibility. Before an optimality extension the team must specify the objective function, direction, optional-job treatment, weights/units, tie-breaking or tolerance and independently verifiable optimal-reference/bound policy. Feasibility, certified infeasibility and abstention remain the present evaluation contract.

The stricter boundary is an additive root module because historical packages bind every original `surgerybench` source hash. Those source files, legacy acceptance behavior and all old corpus/protocol hashes remain unchanged. New consumers must explicitly import `temporal_validation_v2` for schema validation, rendering/parsing, intended-instance checking/scoring and checked solver dispatch, and record its revision/source hash with a new registration. The existing PR23/SDK runner does not silently adopt this revision; its four-case guard and old plan assessability remain intact. A new module cannot enforce adoption by an arbitrary caller still using the frozen legacy entry points.

The [strict offline consumer](strict-temporal-consumer-v1.md) now adopts this boundary end to end for a fixed, separately registered validation cohort; historical and SDK consumers remain unchanged.
