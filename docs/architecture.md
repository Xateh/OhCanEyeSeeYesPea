# Architecture and code map

This guide describes the pilot implementation inspected at `38c34bbbdc8e239dfbb6cf65e6ebbe35aa4937e6`. Proposed extensions are tracked separately in [the roadmap](roadmap.md). The project uses Python's standard library at runtime.

## Data flow and trust boundaries

1. `temporal_dataset.records()` constructs paired schema-1.1 instances, obtains tiny-case oracle labels, validates evidence and renders controlled-language text.
2. `build()` writes model-visible `{id,text}` rows separately from privileged gold rows, plus summary/manifest.
3. `temporal_benchmark.run()` integrity-checks matching rows and invokes a fresh provider for each arm of each case.
4. The no-tools arm has an empty tool list. The CSP arm may call only `csp` with the provider's own translated `instance`.
5. `score()` validates final outputs against the **original gold instance**, outside provider/tool context. A solution to incorrect translated constraints can therefore fail scoring.

This is an interface boundary, not an operating-system security sandbox: an arbitrary installed Python provider runs in the same process and must be reviewed. Do not give a real provider filesystem/gold access or a repair tool as part of the experiment.

## Source modules

| File | Main responsibilities and entry points | Important boundary |
|---|---|---|
| [`__init__.py`](../surgerybench/__init__.py) | Package version `0.1.0` and research-only description | No public service or clinical API |
| [`common.py`](../surgerybench/common.py) | `canonical`, `digest`, `read_jsonl`, `revision` | Revision hashes all package `*.py` contents, not the Git commit or docs |
| [`checker.py`](../surgerybench/checker.py) | Schema-1.0 resource/schedule validation; identifier/integer helpers; legacy certificates | Inclusive **day** release/due semantics; do not pass temporal schema 1.1 directly |
| [`temporal_check.py`](../surgerybench/temporal_check.py) | Schema-1.1 validation, absolute-minute schedule checks and `pair_order_impossible` certificate | `relaxed()` deep-copies into schema 1.0 solely to reuse resource checks; temporal bounds are checked separately |
| [`temporal_text.py`](../surgerybench/temporal_text.py) | `RULES`, canonical `render(instance)`, strict `parse(text)` | Regex parser accepts its own controlled language, not general natural language; used by mock only |
| [`temporal_dataset.py`](../surgerybench/temporal_dataset.py) | `fixture`, `records`, `build`, `audit`; deterministic original synthetic pairs, splits and lineage | Build refuses an existing directory; audit is specific to this 48-case pilot |
| [`temporal_oracle.py`](../surgerybench/temporal_oracle.py) | `enumerate_schedules(instance, limit=100000)`; Cartesian complete assignments | No generator, CSP or checker imports; tiny valid instances only; limit yields UNKNOWN |
| [`temporal_csp.py`](../surgerybench/temporal_csp.py) | `solve(instance,max_nodes=100000,seconds=2)`, `CSPAdapter`, tool definition/revision | Receives translated constraints only; bounded DFS, not OR-Tools |
| [`temporal_benchmark.py`](../surgerybench/temporal_benchmark.py) | `MockProvider`, `run_arm`, `run`, `score`, CLI | Same text/revision across arms; external scoring; logs errors separately |

Both search implementations schedule mandatory jobs only. Optional jobs can be omitted under the feasibility semantics; neither maximizes optional coverage or priority. The schema checker accepts a broader range than the tiny generated corpus tests.

## Supporting segments

- [`fixtures/arrival-deadline-v1/`](../fixtures/arrival-deadline-v1): immutable original `model.jsonl`, `gold.jsonl`, `summary.json`, `manifest.json`. Only the first file is model-visible.
- [`scripts/verify_package.py`](../scripts/verify_package.py): audits original and regenerated fixtures, compares two builds byte-for-byte, permits only three original-vs-new build identity differences, checks 24 counterfactual pairs and runs 48 mock pairs. It also checks corrupt fixtures are rejected with optimized Python. Temporary files are removed.
- [`tests/test_temporal.py`](../tests/test_temporal.py): 28 original temporal semantics/oracle/CSP/text/harness tests.
- [`tests/test_package.py`](../tests/test_package.py): 6 fixture/provenance/split/hash tests.
- [`tests/test_regressions.py`](../tests/test_regressions.py): 40 focused malformed-input, optional/gap, token-usage, call-limit, revision and integrity regressions. Subtests are not counted as extra methods.
- [`evidence/`](../evidence): sanitized historical validation/review/hash snapshots. Read their recorded revision, scope and timing; they are not evidence of new execution or real-model quality.
- [`.github/workflows/offline-pilot.yml`](../.github/workflows/offline-pilot.yml): PR-to-main CI on Python 3.10–3.14, running unit tests and package verification; official actions are pinned, repository contents permission is read-only.
- [`pyproject.toml`](../pyproject.toml): optional setuptools package metadata, no runtime dependencies. The wheel path and fixture packaging are not validated by the offline checkout workflow.
- [`.gitignore`](../.gitignore): local output exclusions. Inspect it before adding experiment outputs; ignored paths are not a privacy guarantee.

## Extension checklist

Provider work plugs into `next(text,history,tools)` and a nonempty exact `model_revision`; see [contracts](benchmarking.md). A solver adapter supplies `revision`, `tool_definition` and `invoke(arguments)`; `run(...,adapter=...)` accepts it programmatically (the CLI has no adapter flag).

Before replacing DFS with Allan's framework, agree translated-instance semantics, status mapping, time limits, witness format and how infeasibility will be independently certified. Solver success alone does not establish translation correctness. Keep the checker independent of solver/generator implementation and preserve oracle cross-checks for small cases.

To add data, version the corpus/generator and update coverage, provenance and tests together. Do not mutate the original manifest or quietly widen the pilot's audit contract. Larger problems need a separately justified labeling/validation method; exhaustive enumeration does not scale automatically.
