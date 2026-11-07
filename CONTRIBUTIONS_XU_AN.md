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
