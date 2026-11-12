# Xu An: dataset, validation and benchmark tooling record

This record distinguishes Xu An's project direction and integration responsibilities from implementation assisted by AI and work reused from teammates. It is a contribution record, not a declaration of sole authorship or team acceptance of every proposal.

## Scope and artifacts

Xu An directed the dataset contribution: preserve original fixtures, improve malformed-input and independent evidence checks, standardize model-facing inputs, support seeded numerical and constraint-interaction coverage, and connect validated datasets to the shared benchmark. Xu An chose to retain the 200 admitted v2 cases as a versioned development baseline and expand separately. These decisions do not establish an independent holdout or authorize a model run.

Repository history includes the [Tier A semantics tests, PR16](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/16), [15-case synthetic ledger, PR17](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/17), [offline contract/scorer, PR18](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/18), [execution/completion preparation, PR20](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/20), and [receipt-accounting/reporting fixes, PR22](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/22). Authorship shown by GitHub alone does not establish who personally wrote or reviewed each line.

The current local integration brings forward `development_suites_v2.py`, its separate auditor, lineage/counterfactual tools, v3 interaction constructions, explicit registrations and actual-ID input view. The accepted v2 baseline has 200 admitted cases from 240 candidates; v3 separately has 48 candidates/28 normalized structures and 28 admissions/17 structures. Numerical variants and related constructions are not independent samples. New QA snapshots are byte-identical copies, not additional cases.

New `benchmark_datasets.py`, `paired_runner.py`, `solver_interface.py` and `offline_provider_example.py` connect explicit validated selections to an offline paired run, independent intended-instance checks, fixed denominators, retained failures/usage gaps and a small solver plug-in contract. New tests exercise wrong translations, valid alternate witnesses, optional omission, invalid/unsupported proofs, malformed outputs, UNKNOWN/timeouts, budgets, duplicate/missing receipts and input separation. The companion integration document records verification evidence and limitations; historical test counts must not be treated as fresh results.

## Reused team work

Benjamin's [shared evaluation framework](docs/evaluation-framework.md), merged through [PR19](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/19), supplies the frozen evidence-backed scoring and reporting principles. The integration reuses `tier_a_contract.output_verdict` and the merged completion proposal rather than replacing them or introducing a soft score.

Allan's [PR21](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/21) supplies the harder 100-case corpus and study/provider/prompt/reporting work. Its 50 authored witnesses and 50 compact certificates are distinct from bounded tool support: the separate registration records 51 supported cases and 49 tool-UNKNOWN cases. UNKNOWN does not invalidate a checked gold answer. Any selected supported subset is disclosed separately from full source membership. Allan's duration constants retain the original source attribution and licensing limitations; the external extraction was not reproduced here.

The integration uses the existing merged temporal CSP/checker implementation. It does not implement a replacement solver, claim ownership of Allan's solver responsibilities, or assume an unmerged/new solver exists. The interface is intended to make subsequent solver integration straightforward.

PR22's corrected 64/100 first-attempt successes and 38/40 separate rerun successes are historical recorded observations. No new model experiment produced those figures, and this integration leaves the underlying receipts/results unchanged.

## AI-use declaration

AI assistants generated and edited code, tests, documentation and this record under Xu An's instructions. They also performed source comparisons, synthetic/offline tests, arithmetic/checker review and proposed interface designs. AI assistance is substantial and is not equivalent to independent human review, research-protocol acceptance or clinical validation. Xu An's directions and recorded choices are distinguished above; this record does not claim that Xu An personally wrote, executed or reviewed every artifact.

The present continuation used offline fixtures only. It made no live model/provider call, paid evaluation, training run, new dependency installation or external dataset download. Pending human/team work includes reviewing the local implementation, choosing a study cohort and provider/model, finalizing prompts/serialization, budgets, repetitions, ordering, stopping/retry policy and obtaining separate execution/publication approval. Solver plug-in correctness and provider behavior require their own review; the API separation is not a sandbox against arbitrary same-process code.


## Provider integration revision

The additive paired runner now has an explicitly opted-in bridge to Allan's merged ClaudeCodeProvider transport, text-tool serializer and usage accounting. AI assistance implemented and mock-tested the bridge, strict raw-output boundary, source/configuration binding and operational-limit diagnostics. Historic prompts/parser and study results remain preserved. The minimal merged-provider edit adds optional timeout and exit-status observation parameters; historic defaults remain unchanged. This reuses Allan's contribution rather than claiming a new provider implementation.

This revision has no live provider validation, prompt transmission, credential use or paid execution. Configuration and an opt-in are software requirements, not human/team sign-off or research authorization. Xu An's direction and integration contribution should be reviewed by the team; substantial AI-authored code, tests and documentation must not be represented as personally written or independently human-verified work. See docs/paired-provider-integration-v2.md for serialization, accounting and enforcement limitations.


### Provider correctness follow-up

AI-assisted offline regressions reproduced a missed per-call cost overrun and a mismatch between emitted and assessable receipt sizes. The local correction adds per-call observation/allocation joins, explicit overrun failures and shared bounded receipt/archive handling. Original raw/error/usage evidence is retained; oversized unparsed evidence is explicitly marked opaque and cannot be treated as successful evidence. Accounting, strict JSON, retention code and runtime identities are pinned. This remains AI-assisted software validation with no live calls, human sign-off or publication. Earlier test counts belong to their recorded revisions; the follow-up has its own evidence record.


## Direct API format and counterbalanced ordering

Following Xu An's approved format change, AI assistance implemented a separate direct OpenAI Responses transport, versioned paired runner, counterbalanced arm ordering, key-free environment template and explicit future key-file loader. The API preserves the shared case text and application-owned JSON CSP protocol, frozen intended-instance evidence scoring and every planned failure/missing slot. It reuses the merged checker, CSP and shared text formatter; Allan's historic CLI experiments remain a separate protocol. Original runner/source dependencies and trial artifacts are preserved.

Code/tests/docs in this revision are substantially AI-assisted and require human/team review. Verification uses synthetic HTTP responses and synthetic test keys only; no real credential is read, no entitlement or billing is verified, and no live API/model call or paid trial is run. Dollar fields are estimates from pinned rates, not confirmed charges. Existing ChatGPT plan/API-credit possibilities remain unconfigured. The supplied .env.example is empty; persistent credential setup and real execution need separate authority. This record does not claim personal sole authorship, human sign-off, research acceptance or new model results.


## 7 November: SDK migration and recorded development checks

Under Xu An's direction, AI assistance prepared a separate official OpenAI Python SDK transport, dependency lock, request/response parity tests and protected local execution boundary. Historic HTTP protocols and outcomes remain intact; the SDK itself has only offline/mock validation. This is substantial AI-authored integration/testing work, not independent human sign-off or solver authorship.

The preceding HTTP implementation did complete separately approved development pilots, including a selected four-case Astra comparison and final-handoff/schema diagnostics. Those measurements and corrected usage estimates are preserved in versioned xlogin evidence; earlier paragraphs saying no live API calls describe their own revision, not the later record. Selected repeated development cases do not establish general accuracy, a holdout, optimality or a CLI/API causal effect. Benjamin retains protocol/analysis ownership, Allan solver ownership, and Xu An dataset/validation/harness integration. Any broader run or publication needs its own applicable approval.


The SDK review repair adds bounded partial-response retention, distinct streaming-timeout outcomes, explicit encoding rejection, checked-in synthetic regression fixtures and a dedicated optional-SDK CI job. AI assistance implemented and tested this work; coordinating code review is complete and PR publication is separately authorized. This does not claim independent human/team sign-off. No further model calls or new research outcomes were produced.


## 7 November: local dataset/benchmark boundary follow-up

Under Xu An's direction, AI assistance reproduced and corrected temporal-schema container/unknown-field validation through the explicitly selected temporal_validation_v2 boundary, preserving the frozen original modules, and made the omitted-emergency normalization explicit. It added offline boundary/invariance and intended-instance checks, retaining an oracle-infeasible/solver-UNKNOWN stratum. This local follow-up does not alter PR23, historical corpus/results or SDK calibration guards. No model calls or publication were performed. No optimization objective was invented; team agreement on that contract remains necessary. This is AI-assisted implementation/testing, not independent human review or sole solver authorship.

The local continuation also connects strict v2 to a separately versioned offline validation consumer, reusing existing paired execution/accounting and the merged CSP boundary. Allan retains solver/frontier-model integration responsibilities. AI assistance implemented registration, payload isolation, strict translated-input dispatch, intended-instance final scoring and failure-denominator tests. This is software integration evidence only; the default mock abstentions and checked fixture outputs are not new LLM results. No optimality objective, teammate commitment, live run or publication is claimed.


## Local P2 follow-up after PR23 merge

AI assistance under Xu An's direction reproduced and locally corrected planned-cost denominator gaps, dataset pre-read bounds and legacy HTTP partial-read/redaction failures. Verification uses synthetic data and Slurm offline jobs, not model experiments. Original source/fixture/result identities are preserved or explicitly versioned for replay; no token, live call, publication or new solver is involved. This local engineering work remains subject to review and does not establish human sign-off or research conclusions.


## 12 November 2026: direct Python API workflow (local revision)

At the user's request, substantial AI-assisted implementation adds explicit official OpenAI/Anthropic SDK selection, retaining the historical Claude CLI separately. A new version uses one model response per arm: baseline final evidence, or model-authored CSP translation followed by checked Python solver evidence and independent original-instance evaluation. It does not ask the model for a second final. Data/IDs and historical protocols/outcomes remain unchanged. The README is rewritten for project users, with detailed implementation and validation material linked separately.

This work is baseline integration/dataset-validation support; Allan's solver ownership and team protocol/analysis responsibilities are not reassigned. No optimality objective is invented. AI generated and reviewed source, tests and documentation under the user's direction; this is substantial AI assistance, not a claim of independent personal authorship or human sign-off. Tests use synthetic keys, fixtures and mocked transports. At that initial offline checkpoint, no live calls, dependency installation or publication had occurred. The subsequent SDK and live checkpoints are recorded below.


### 12 November 2026 integration follow-up

AI-assisted source integration preserves 26 additive PR26 files from merged main a8621d2, verified against 275 upstream blobs, alongside the local direct API work. This is not a Git ancestry merge or a reinterpretation of Allan's historical results. The direct backend remains bounded DFS; OR-Tools defaults are not substituted. An isolated actual Anthropic 2.8.0 SDK check passed with synthetic credentials and mocked HTTP, not a live model call. Existing team ownership, substantial AI-assistance declaration and lack of human sign-off remain applicable.


### 12 November 2026 approved OpenAI pipeline smoke

Under the user's explicit approval, AI assistance executed and assessed the bounded direct OpenAI workflow on four reused original-synthetic development cases. Astra/high Standard completed all eight slots with four independently evidence-valid results per arm, eight model calls, four checked Python DFS calls and zero post-solver model calls. Reported usage gives a US$0.16960 estimate, not verified billing. No retry, output repair, historical-result change, optimality claim or publication occurred. The separate actual Anthropic SDK check used synthetic credentials and mocked HTTP, not live Anthropic inference.

AI assistance updated the user-facing README and direct-workflow guide to reflect this narrow verification. This remains baseline integration/dataset-validation work; Allan's solver ownership and team protocol/analysis roles are unchanged. These reused development cases do not establish holdout performance, general accuracy or solver superiority. Full legacy-suite verification remains incomplete. Tested code/receipt hashes are preserved; documentation-only changes have a separate review record. The substantial AI declaration and absence of human sign-off remain applicable.


### Pre-publication saved-assessment review

AI-assisted review reproduced and corrected a conditional saved-evidence join bypass, with focused offline regressions. Assessor revision direct-saved-evidence-joins-v2 rejects missing evidence and missing raw/model joins without dropping legitimate failed attempts. Generation/provider/solver functions and model requests are unchanged. The earlier live smoke remains tied to its actual tested source; the later assessor correction is not claimed as newly live-tested. Historical receipts and source pins are preserved, with a separate offline compatibility recheck. Relative links in the newly copied history document were corrected without changing historical commands/results.
