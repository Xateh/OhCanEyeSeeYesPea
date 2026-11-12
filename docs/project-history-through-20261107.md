# Historical project README (preserved 12 November 2026)

This is a dated historical snapshot, not current setup guidance. Use [the project README](../README.md). Relative links are adjusted from the original README root; historical claims and commands remain unchanged.

# OhCanEyeSeeYesPea

CS3263 Group 7 research prototype: compare the **same language model on identical surgery-scheduling text**, without tools versus with a CSP tool that receives the model's translated constraints. An independent checker scores the intended instance outside both arms.

## Current reviewed integration (7 November 2026)

The current addition provides an official OpenAI Python SDK path for model-alone versus mandatory model-plus-CSP calibration. See the [SDK usage guide](../docs/openai-sdk-integration-v1.md) and [paired-runner integration guide](../docs/paired-runner-integration.md). SDK v2 has offline/mock verification only: 434 distinct tests passed normally and the same 434 under optimized Python in a clean copy, including 13 SDK tests. Live SDK behavior is not yet validated. The SDK entry point currently retains the four-case calibration guard and pinned CPython 3.12/Linux environment; it does not provide arbitrary-cohort execution or optimality scoring. Historical raw-HTTP development pilots and protocols remain separate and unchanged.

## Original proof-pilot status (historical)

This branch contains an **original-synthetic, offline proof pilot**, originally proposed in [PR #1](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/1). It is not a clinical system or a completed real-model study.

- 48 controlled-language cases in 24 paired families: 24 feasible and 24 certified infeasible; 2–3 mandatory surgeries per case.
- Family-disjoint train/validation/test splits of 32/8/8 cases, with deliberate parameter ordering rather than random IID sampling.
- A bounded standard-library DFS CSP adapter, independent schedule/certificate checking, and a separate tiny-case Cartesian oracle.
- A provider-neutral paired harness with a deterministic **mock** translator. No real LLM/provider is included or selected; no model-performance results are established.
- 74 test methods plus fixture audit, regeneration and 96 mock arm runs. [Baseline PR CI for head 38c34bbb](https://github.com/Xateh/OhCanEyeSeeYesPea/actions/runs/39037869399) passed on Python 3.10–3.14 using GitHub's PR merge checkout. Consult current PR checks for later commits.

The larger historical corpus is not in this repository. No source-derived/IHTC data is included, and its redistribution rights remain unresolved. OR-Tools integration, broader dataset coverage/difficulty validation, prompts, matched evaluation budgets and real-model experiments are still planned.

## Quick start

Use Python 3.10 or newer from this repository's root on `feat/arrival-deadline-pilot`. Runtime and tests use only the standard library; no installation, API key or model download is required.

```bash
git clone --branch feat/arrival-deadline-pilot https://github.com/Xateh/OhCanEyeSeeYesPea.git
cd OhCanEyeSeeYesPea
python3 -m unittest discover -s tests -v
python3 -m scripts.verify_package
```

To retain a mock run, choose a new output path:

```bash
python3 -m surgerybench.temporal_benchmark \
  --model fixtures/arrival-deadline-v1/model.jsonl \
  --gold fixtures/arrival-deadline-v1/gold.jsonl \
  --out runs/mock.jsonl
```

The mock no-tools arm deliberately returns UNKNOWN. Its assisted arm exercises translation/tool/checker integration. These outputs **do not compare actual LLM ability**. Commands refuse to overwrite existing output files.

## Documentation

- [Pilot runbook and validation boundaries](../PILOT.md)
- [Architecture and code-module map](../docs/architecture.md)
- [Dataset, schema and scheduling semantics](../docs/data-and-semantics.md)
- [Provider/tool contracts, scoring and experiment workflow](../docs/benchmarking.md)
- [Shared evaluation framework](../docs/evaluation-framework.md)
- [Roadmap and team review gates](../docs/roadmap.md)
- [Provenance and publication exclusions](../PROVENANCE.md)
- [Open work](https://github.com/Xateh/OhCanEyeSeeYesPea/issues)

## Research scope and team interfaces

The original proposal concerned university timetabling; the post-consultation prototype focuses on abstract surgery scheduling. Each surgery has a fixed surgeon, nonpreemptive deterministic duration, arrival/completion bounds and eligible operating rooms. Calendars, daily minute budgets and resource gaps are explicit. Priority/emergency metadata does not imply an optimization objective or clinical priority policy.

The [proposal and progress document](https://docs.google.com/document/d/1A1CfuLvvGqqFIVxMyThe0pkc4jgBMG6oruXJizW-Nsw/edit) records Xu An's problem/dataset role, later expanded to benchmark tooling; Allan's OR-Tools framework role; and Benjamin's prompting, experimental analysis and Responsible AI role. Integration and final scope need team agreement. Issue role suggestions are discussion context, not new assignments.

## Safe development

Keep model-facing text separate from gold instances, labels and evidence. Never expose gold/scoring to a model or silently repair a translation with it. Add regression tests when changing constraints, proof semantics or adapters. Preserve original fixtures/provenance and use new output paths. Do not infer INFEASIBLE from a timeout or unsupported proof.

Before real runs, agree the provider/model revision, prompts, budgets, retry limits, logging/privacy and spend authorization. No clinical use or real patient data is supported. See [LICENSE](../LICENSE) and [PROVENANCE.md](../PROVENANCE.md); the original-code/synthetic-data license does not grant rights over excluded third-party material.
