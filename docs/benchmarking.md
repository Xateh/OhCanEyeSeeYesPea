# Benchmark and integration contracts

## Runnable offline workflow

From the checkout root with Python >=3.10:

```bash
python3 -m unittest discover -s tests -v
python3 -m scripts.verify_package
python3 -m scripts.verify_package --out runs/verification-new.json
python3 -m surgerybench.temporal_benchmark --model fixtures/arrival-deadline-v1/model.jsonl --gold fixtures/arrival-deadline-v1/gold.jsonl --out runs/mock-new.jsonl
```

Outputs must not already exist. Verification uses temporary data and runs 48 pairs/96 mock arms; retained mock logs are created only by the explicit benchmark command. Historical evidence and CI must be attributed to their exact revision, not described as newly executed.

The default `MockProvider` parses canonical controlled language and is **not an LLM**. No-tools returns UNKNOWN; assisted translates once, calls CSP and forwards supported result fields. This verifies plumbing and independent scoring only.

## Provider contract

Supply a zero-argument factory returning a fresh provider for each case/arm:

- `model_revision`: exact, nonempty string, identical across all factories/arms/cases in a run
- `next(text, history, tools)`: returns a Python dictionary as described below
- `text`: same natural-language string for both arms, unchanged across turns
- `history`: prior tool invocations/results only, containing `name`, `arguments`, `result`, `latency_seconds`; not a complete provider chat transcript
- `tools`: [] for no-tools; a one-element list containing the CSP tool definition for assisted

A provider requiring conversation state owns that state internally. No real SDK, authentication, model selection, network retries, timeout enforcement or token budget policy is supplied. A provider module is executable Python, so review it before import and keep gold inaccessible by design.

Messages:
```json
{"type":"final","output":{"status":"UNKNOWN"},"usage":{"input_tokens":10,"output_tokens":2}}
```
or:
```json
{"type":"tool_call","name":"csp","arguments":{"instance":{"schema_version":"1.1"}},"usage":null}
```
The second example only illustrates the envelope: `instance` must contain the **complete** schema described in [data semantics](data-and-semantics.md).

Final output is one of:
- `{"status":"FEASIBLE","schedule":[{"patient":"A","day":0,"start":0,"room":"r0"}, ...]}`
- `{"status":"INFEASIBLE","certificate":{"kind":"pair_order_impossible","patients":["A","E"]}}`
- `{"status":"UNKNOWN"}`

The provider extension point is:
```text
--provider package.module:factory
```
This imports the named factory; it is not permission to choose a model or incur API costs.

## Tool and call limits

`CSPAdapter` exposes `revision`, `tool_definition`, `invoke(arguments)`. The only accepted argument key is `instance`; passing text or gold lookup IDs is rejected. The provider translates from text. No repair/checker/scoring tools are exposed.

`run_arm(..., max_calls=4)` allows at most four executed tool calls and up to five provider responses, including the final turn after the fourth call. An attempted extra tool call becomes a provider/parse error without invocation; reported usage on that attempt still counts. No-tools cannot invoke any tool. The top-level CLI/run uses this default; it does not expose a call-limit option.

The stdlib DFS defaults to 100,000 nodes/ticks and 2 seconds, with periodic checks. It returns a valid witness, a supported contradiction or UNKNOWN. It is not OR-Tools and its bounded time limit is not an end-to-end provider timeout. A replacement adapter can be passed to `run(..., adapter=...)` programmatically after the team agrees the contract.

## Integrity and leakage controls

Before invoking providers, `run` checks duplicate IDs, model/gold ID equality, exact model-row keys, text/instance hashes and provider revisions. It does not replace the full dataset `audit`; run package verification first.

Only model text and permitted tool history are given to each provider; gold instance, labels, witnesses and scores remain in external evaluation. Never correct a model's constraints using gold. Solving the mistranslated problem successfully can still fail against intended constraints. A future adapter must not parse gold through an indirect route.

The current harness gives both arms equal text/model revision and tool availability differs; it does **not yet enforce** matched prompt templates, tokens, wall-clock budgets, repetition seeds or retry budgets for real providers. Record and agree these before real experiments.

## Logs and metrics

Each JSONL row records case/family/split/arm, text hash, model/tool/code/data/gold revisions and Python version, plus:
- final output, structured provider responses, tool arguments/results/count and latency
- total arm latency
- token usage or null and an explanation
- errors with `provider_or_parse` or `tool` stage and corresponding booleans
- independent `score` with violations and outcome flags

Token usage is summed only when every provider response reports both nonnegative integer `input_tokens` and `output_tokens`. Missing, partial, malformed usage or an exception makes the total unknown, not zero. Zero is valid when explicitly reported.

Metrics should be aggregated separately per arm:
- `feasible_schedule_success`: denominator is gold-FEASIBLE cases
- `infeasible_decision_correct`: denominator is gold-INFEASIBLE cases; status matches, even without proof
- `infeasible_certified_success`: same gold-INFEASIBLE denominator, but needs independently valid proof
- UNKNOWN, invalid-output, provider/parsing error and tool error rates: report denominator explicitly, ordinarily all attempted cases
- violation counts/types, latency and known-usage coverage; distinguish missing token totals from measured zero

`valid` means an accepted schedule/certificate, not identical to every accuracy metric. UNKNOWN is not an invalid schema but not success. Errors may coexist with a later final answer, so do not silently discard errored runs. No aggregate statistical analysis, confidence intervals or soft-objective score is implemented.

## Real-experiment readiness gates

1. Team agrees final formulation, dataset version/coverage/difficulty and family holdouts.
2. Solver contract is agreed with Allan; independent checks cover broader cases.
3. Benjamin/team freezes prompt conditions, output policy, metrics, matched budgets and repetition/seed plan; Xu An's benchmark tooling implements the agreed controls.
4. Team selects provider/revision and obtains specific spending/data-sharing authorization. A contract-tested provider must fail safely on malformed output, unsupported tools, missing usage, timeouts and revisions.
5. Run a bounded authorized pilot before the full paired study. Preserve raw logs privately; publish only approved sanitized evidence and reproducible configuration.
6. Analyse paired/family-aware results and errors; discuss difficulty limits, synthetic realism, fairness, explainability, human accountability and privacy. No clinical-readiness or proven-bias-free claim.

See [roadmap](roadmap.md) for dependencies. Preparing these gates does not itself authorize real API calls.
