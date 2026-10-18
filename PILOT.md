# Original-synthetic arrival/deadline pilot

This branch adds a self-contained 48-case CS3263 pilot, published for review in
[draft PR #1](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/1) in the private
repository. The project README and component guides document this pilot; the PR
remains unmerged. Original fixture provenance and repository history are retained.

## Run offline

From the repository root, with Python 3.10 or newer:

```bash
python3 -m unittest discover -s tests -v
python3 -m scripts.verify_package
```

The current suite has **74 test methods**: 28 original temporal tests, 6 package
checks, and 40 focused checker/harness regressions. Subtest combinations are not
counted as additional methods. The standalone 63-test suite also had 35 v1 tests;
those v1 modules/data are not reintroduced. Relevant generic coverage was adapted
using only original-synthetic fixtures. The initial package had 34 tests.

Focused coverage includes malformed schedules/certificates, optional-job rules,
positive-gap boundaries, complete/incomplete/invalid token usage, provider and
tool failures, call-limit boundaries, same-model revision checks across arms and
cases, hash integrity, forbidden gold fields and output overwrite protection.
Model revisions must be nonempty strings. Missing usage after a malformed response
or provider exception makes the aggregate unknown, rather than reporting a partial
total as complete. Reported usage on a rejected extra tool call still counts.

GitHub Actions runs these same commands on Python 3.10, 3.11, 3.12, 3.13 and
3.14 for pull requests to main. The workflow uses pinned official actions and
read-only contents access. Tests install no dependencies and download no data or
models; checkout and Python setup may access GitHub. See the PR checks for current
results. Historical evidence retains the versions and local-only status at the
time of those runs. Optional wheel builds, exhaustive malformed-input fuzzing and
real-provider integration remain outside this validation.

There are no runtime dependencies beyond the standard library and no installation
step. `pyproject.toml` describes optional packaging; building a wheel additionally
needs setuptools. The verification command audits all fixtures, independently
enumerates all 48 cases, regenerates twice, compares the generated cases with the
original fixtures, and runs 48 offline pairs (96 arm runs). Temporary outputs are
removed automatically. To retain a sanitized summary, pass `--out NEW_FILE.json`.
The command refuses to overwrite an existing output file.

For an individual mock run:

```bash
python3 -m surgerybench.temporal_benchmark \
  --model fixtures/arrival-deadline-v1/model.jsonl \
  --gold fixtures/arrival-deadline-v1/gold.jsonl \
  --out runs/mock.jsonl
```

The default provider is a deterministic controlled-English translator, **not an
LLM**. These results test integration and validators, not model performance.
No API credentials, real model adapters, network calls or repair tools are used.

## Data and splits

All 48 cases are original synthetic: 24 base families, each with a feasible case
and a counterfactual changing only E's completion deadline by minus one minute.
Four themes each have six families: tight windows, room contention, fixed-surgeon
contention and eligible-room bottlenecks. These small, parameterized cases have
2–3 surgeries, and the categories overlap. They are a bounded proof pilot, not a
broad clinical or operational dataset. No paraphrases increase the count.

| Split | Families | FEASIBLE | INFEASIBLE | UNKNOWN |
|---|---:|---:|---:|---:|
| Train | 16 | 16 | 16 | 0 |
| Validation | 4 | 4 | 4 | 0 |
| Test | 4 | 4 | 4 | 0 |

Related pairs stay in one split. Per theme, indices 0–3 train, 4 validation, 5 test;
duration increases with index, so this is not a random IID split. Each family has
an independent recorded seed. Keep `gold.jsonl` and all evidence outside model
context: only `model.jsonl` supplies model-visible `id` and `text`.

The fixture bytes are identical to the approved original pilot. Packaging extracts
serialization and revision helpers into `common.py` to remove dependencies on the
larger corpus/adaptation modules. Consequently, a fresh build records a different
code revision (and possibly Python version), changing lineage-derived case IDs.
Verification permits exactly those three build-identity fields to differ: `id`,
`lineage.code_revision`, and `lineage.python`. All other content—including text,
instances, labels, witnesses, certificates, family membership, seeds and splits—
must match exactly. Two builds under the same packaged revision are byte-identical.
Original fixture provenance is preserved rather than rewritten to claim this code
revision generated the earlier artifacts.

## Exact semantics and certificates

Schema 1.1 reuses `release` and `due` as absolute integer minutes from day 0:
`day*1440 + start >= release`; `day*1440 + start + duration <= due`.
Schema 1.0's inclusive day windows are not reinterpreted; the legacy checker is
used only as a resource-constraint validator through an explicit relaxed view.
No duplicate arrival/deadline fields are introduced.

A mandatory surgery occurs exactly once; an optional surgery may be omitted and
otherwise occurs at most once. Pilot surgeries are all mandatory. Fixed surgeon,
nonpreemptive duration, eligible room, daily minute budgets, required gaps within
each resource/day and resource availability apply. The shipped cases use zero gaps;
positive gaps are covered by focused regression tests. Entire half-open intervals `[start,end)` must fit
one availability window. Adjacent surgeries are allowed when the resource gap is
zero. Splitting an operation is invalid. Emergency flags and priority are metadata
with no unstated constraints. Daily budgets are not availability calendars.

Every feasible witness passes an independent checker. Every infeasible case has a
checkable `pair_order_impossible` contradiction: two mandatory jobs forced to share
a resource cannot fit in either order even with calendars, budgets and gaps relaxed.
A separate Cartesian oracle completely enumerates these tiny fixtures. Limits yield
UNKNOWN, never an inferred infeasible label. The CSP also returns UNKNOWN after
exhaustion when it lacks a supported compact certificate.

The required regression has one room `[0,10)`, distinct surgeons, A arriving 0 with
duration 4/deadline 10 and E arriving 3 with duration 4/deadline 8. Its unique
schedule is A `[0,4)`, E `[4,8)`. Reducing E's deadline to 7 is infeasible despite
only 8 minutes of work; splitting A into `[0,3)` and `[7,8)` is rejected.

## Paired benchmark interface

Providers expose `model_revision` and `next(text, history, tools)`. Both arms get
the identical natural-language text and same provider revision. The no-tools arm
receives no tools. The CSP arm receives only `csp`, accepting a schema-1.1 instance
translated by the provider from that text. The tool cannot retrieve privileged
gold. Scoring against the intended original instance happens outside both arms.
A solver-valid schedule for mistranslated constraints can therefore fail scoring.

Messages return either `type: final` with `output`, or `type: tool_call`, `name: csp`,
`arguments: {instance: ...}`. Optional usage is `{input_tokens, output_tokens}`.
`--provider module:factory` is the extension point for a separately authorized
provider integration; none is included here. The tool is the bounded stdlib DFS
adapter in `temporal_csp.py`.

Logs record structured responses, constraints, calls/results, violations, latency,
token use (null when unreported) and exact model/tool/code/data revisions. Metrics
separate feasible schedule success, infeasible decision correctness, certified
infeasible success, UNKNOWN, output errors and provider/parsing/tool errors. Report
arm-specific denominators by gold label. The mock no-tools UNKNOWN responses are
not evidence that an actual LLM cannot solve the problems.

## Provenance and exclusions

See `PROVENANCE.md` for the explicit inclusion boundary, original hashes and source
relationship. The original server workspace and corpus v1 were preserved. This
checkout neither needs nor includes their data. It includes no IHTC/source-derived
instances, source archives, official validator, credentials, private raw logs,
server paths, unrelated files or Library attachments. The original source-data
license uncertainty is not resolved by this package. No clinical use or real
patient data is involved.
