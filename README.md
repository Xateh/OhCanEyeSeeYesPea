# OhCanEyeSeeYesPea

Compare a language model alone with a model whose translated surgery-scheduling constraints are executed by a checked Python CSP solver. Both arms are evaluated against the **original intended problem**. The current contract measures feasible schedules and supported infeasibility certificates, not optimality.

## Start without an API key

Run from the repository root with Python 3.10 or newer. The deterministic demonstration needs only the standard library and makes no network calls. Choose a new output directory; existing results are never overwritten.

```bash
python3 tools/run_direct_benchmark.py --demo --config docs/direct-api-settings.example.json --out runs/direct-demo
python3 tools/run_direct_benchmark.py --assess runs/direct-demo
```

This is a **mock demonstration, not model performance**: its baseline deliberately returns UNKNOWN; its assisted response is a deterministic translation. The fixture data is the checked-in duplicate in `fixtures/responses-offline-v1/seeded-v2/`.

## Choose a provider

| Choice | Entry point | Dependency |
| --- | --- | --- |
| OpenAI API | `tools/run_direct_benchmark.py`, `provider: openai_api` | Official OpenAI SDK; existing pinned CPython 3.12/Linux environment described in [SDK setup](docs/openai-sdk-integration-v1.md) |
| Claude API | Same direct entry point, `provider: anthropic_api` | Official Anthropic SDK; [setup and exact protocol](docs/direct-api-workflow-v1.md) |
| Claude CLI | Existing `tools/run_paired.py` with the explicit CLI adapter configuration | Claude CLI; [legacy paired guide](docs/paired-runner-integration.md) |

The CLI remains a separate historical workflow, not an automatic fallback. Selecting an API never invokes the CLI. On 12 November 2026, a bounded OpenAI Astra/high Standard smoke check completed all eight slots on four reused synthetic development cases: four evidence-valid results per arm, eight model calls, four Python DFS calls and zero post-solver model calls. The usage-based estimate was US$0.16960, not verified billing. Claude API has an installed-SDK offline/mock compatibility check only, not live validation. See the [verification scope and receipts](docs/direct-api-workflow-v1.md#verified-smoke-check).

## Inputs and configuration

The direct runner retains the existing **four-case, one-repetition calibration registration**, not arbitrary-corpus execution. On the project server its unchanged source directory is `/home/t/tehxa/cs3263-review/seeded-development-v2-96-20261105/`. The same four cases run once in each arm, with balanced starting-arm order.

Prepare a fresh registration against that existing directory; this reads and validates data but does not generate or modify cases:

```bash
python3 tools/run_direct_benchmark.py --prepare-datasets /home/t/tehxa/cs3263-review/seeded-development-v2-96-20261105 --write-spec direct-datasets.json
```

Copy `docs/direct-api-settings.example.json` to your own configuration. For live use, set `mode` to `live`, select `openai_api` / `gpt-6-astra` or `anthropic_api` / `claude-opus-5-5`, and supply current Standard-tier per-million-token rates and their source. Zero placeholder rates fail closed in live mode. The verified OpenAI smoke allocation used `max_output_tokens: 1700`; the 2,000-token template default exceeded the per-call reserve for these inputs at the checked rates. High reasoning and conservative limits are explicit; these are provisional settings, not an agreed research protocol. See the [configuration contract](docs/direct-api-workflow-v1.md).

Keep the existing key in a separate owner-only, Git-ignored file: `OPENAI_API_KEY=...` for OpenAI or `ANTHROPIC_API_KEY=...` for Claude. Templates: [.env.example](.env.example) and [Claude template](docs/anthropic.env.example). Do not put secrets in settings, command arguments or results. Credential setup and paid execution need appropriate account authorization; a ChatGPT/Claude subscription alone does not establish API entitlement.

Once the account, key use and bounded run are authorized:

```bash
python3 tools/run_direct_benchmark.py --datasets direct-datasets.json --config direct-settings.json --out runs/direct-live --allow-live --allow-key-file --key-file .env.anthropic
python3 tools/run_direct_benchmark.py --assess runs/direct-live
```

For OpenAI select its provider/model in the settings and use the corresponding key file. The command above is a credential-dependent usage example, **not a live Claude run performed here**. No API fallback or retry occurs. Software spend reserves are estimates, not a guaranteed billing cap.

## What each arm does

- **Model alone:** Python sends one composed user prompt; the model returns a strict JSON final answer; the independent checker evaluates it. No solver is exposed or dispatched.
- **Model + CSP:** Python sends one composed user prompt; the model returns a JSON CSP instance; Python validates and invokes the existing checked solver at most once, then evaluates the solver evidence against the original problem. There is **no second model call**.

The prompt contains the unchanged case text plus shared semantics and arm-specific JSON-format instructions. It is not merely the raw problem text. There is no separate system message or native API tool registration. The assisted workflow is a separately versioned treatment from earlier model-after-solver protocols.

## Results

Each new output directory contains `plan.json` (frozen selection, settings and source identities), `attempts.jsonl` (responses, usage and stage receipts) and `summary.json` (all eight planned slots, including missing/failed ones). Assessment reads saved evidence without calling a model or rerunning the solver. Source or dataset drift is rejected.

FEASIBLE requires a valid schedule; INFEASIBLE requires a supported certificate. UNKNOWN is an abstention, not proof of infeasibility. Format validity and semantic evidence success are distinct. The direct solver is the existing bounded DFS adapter. The separately imported [historical OR-Tools workflow/results](docs/ortools-results.md) use the Claude CLI and a post-solver model final; they are not this direct API workflow. Its default eight-worker/ten-second solver is not enabled here. The assisted arm includes local solver compute, so this is a workflow comparison rather than matched total compute.

## Other workflows and references

- [Strict offline schema/round-trip benchmark](docs/strict-temporal-consumer-v1.md)
- [Direct API prompts, limits and accounting](docs/direct-api-workflow-v1.md)
- [Earlier SDK integration](docs/openai-sdk-integration-v1.md)
- [Historical project notes](docs/project-history-through-20261107.md), [contribution and AI-use record](CONTRIBUTIONS_XU_AN.md)

Development fixtures and selected historical pilots do not establish general accuracy or a clean holdout. Source-derived material remains excluded while redistribution rights are unresolved. Report/video submission is a separate team deliverable.
