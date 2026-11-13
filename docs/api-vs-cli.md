# Running a frontier model through its SDK

`study/run_api.py` reruns the recorded Claude Code CLI experiments through an official SDK.

- **`--provider openai`:** GPT-6 Astra through the OpenAI SDK. This is the run the team chose, to test a second frontier model.
- **`--provider claude`:** Claude Opus 5.5 through the Anthropic SDK. This is ready, for a pure CLI vs API check if someone gets an Anthropic key.

**Kept the same as the Claude CLI runs:** the frozen v3 system prompt and user message, word for word; high effort; the same 48 + 100 problems and repetitions (final test 3×); the same OR-Tools solver; and the same scoring under `evaluation-framework.md`. The model asks for the solver in its JSON reply, as in the CLI runs; no native tools are offered.

## Setup (once)

1. Put the key in an owner-only, gitignored file. Never paste it into chat or code.
   - **OpenAI:** `.env` with one line, `OPENAI_API_KEY=...`, then `chmod 600 .env`
   - **Anthropic:** `.env.anthropic` with one line, `ANTHROPIC_API_KEY=...`, then `chmod 600 .env.anthropic`
2. Install the SDKs and OR-Tools: `.venv/bin/pip install openai==3.46.0 -r requirements-anthropic-sdk.txt ortools`

## Run

Smoke test (2 problems, about 2 cents with GPT):
```
.venv/bin/python -m study.run_api --provider openai --arm alone --cohort pilot-validation --budget 1 --limit 2
```

Every cohort, both arms. Each command can be run again to resume; it only runs slots never attempted.
```
for cohort in pilot-train pilot-validation pilot-test hard-n05 hard-n10 hard-n20 hard-n40 hard-n80; do
  for arm in alone ortools; do
    .venv/bin/python -m study.run_api --provider openai --arm $arm --cohort $cohort --budget 10
  done
done
```

A run stops early at the `--budget`, at a rate or quota limit, or when a cost is unknown. Failed attempts stay recorded and count, as the framework requires.

## Compare

```
.venv/bin/python -m study.api_report --provider openai
```

It prints the SDK model next to the Claude CLI for each dataset and arm, and the solver effect within the SDK model. It writes `study/results/api-openai-vs-claude-cli-summary.json`, and reports only complete cohorts.

**Claude CLI side:** Claude alone on the harder set uses the view with reruns (98/100). On first attempts, 36 runs (16 at 40 surgeries, 20 at 80) were refused by the Claude account's 5-hour usage limit, each in about 2 s with no reply recorded.

## Limits

- **Costs are estimates** at standard rates, not the bill:
  - GPT-6 Astra: $10 / $50 per million input / output tokens
  - Claude Opus 5.5: $4 / $20 per million input / output tokens
- **SDK retries:** up to 2 on transient errors (the SDK default); calls time out after 300 s, as in the CLI runs.
- **No refusal fallback:** refused, cut-off or wrong-model replies count as failures. The Claude refusal fallback is not enabled, because a reply from another model would break the comparison.
- **Different from Xu An's flow:** this is not `direct_benchmark.py`. That route sends one message with no system prompt and caps requests at 7,500 bytes, which the 80-surgery problems exceed.
