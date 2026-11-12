# Direct Python CSP API workflow v1

This is a new local protocol, `direct-python-csp-api-v1`, not a relabeling of historical pilots. It removes the second model final step by design. Model input remains the existing case text; evaluator-only intended instances, labels and witnesses are not supplied to the provider.

## Exact prompt and request construction

`direct_benchmark.prompt` concatenates original case text, two newlines, `tier_a_input_view.SHARED`, one newline, then:

- baseline: `study.prompts.SYSTEM_V1`, newline, `FINAL_SHAPE`;
- assisted: `direct_benchmark.TRANSLATE` followed by canonical JSON of `surgerybench.temporal_csp.TOOL`.

Despite the historical constant's name, SYSTEM_V1 is inside the sole user message, not a system role. The final envelope is `{"type":"final","output":OUTPUT}`. The assisted envelope is `{"type":"tool_call","name":"csp","arguments":{"instance":INSTANCE}}`. This is application-owned text JSON, not native tools. Format instructions and instance schema are part of the composed user prompt. Neither provider uses generation-time structured-output constraints in this version: strict parsing and evidence checks follow generation, without repair or retries. This deliberate version must not be pooled with older schema-constrained protocols.

OpenAI uses the official SDK Responses API with `input:[{"role":"user","content":PROMPT}]`, `tools:[]`, `store:false`, `stream:false`, `reasoning.effort:high`, `service_tier:default` and `max_output_tokens`. No `instructions` field is sent. The retained isolated OpenAI helper supplies bounded receipts, explicit endpoint, zero SDK retries and local child deadline.

Claude uses the official Anthropic SDK Messages API, `https://api.anthropic.com/v1/messages`, with `messages:[{"role":"user","content":PROMPT}]`, `stream:false`, `max_tokens`, `service_tier:standard_only`, `thinking.type:adaptive`, and `output_config.effort:high`. No `system` or native `tools` field is supplied. SDK retries are zero; redirects, ambient proxies and telemetry are disabled. Raw bytes, safe metadata and available usage are retained within bounds and credential redaction.

Official references: [Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python), [Messages](https://platform.claude.com/docs/en/api/messages/create), [pinned SDK](https://github.com/anthropics/anthropic-sdk-python/tree/v2.8.0). Documented support does not establish entitlement or live validation.

## Optional environments and keys

The deterministic demo requires Python 3.10+. The OpenAI pinned environment is documented in [SDK integration](openai-sdk-integration-v1.md). For Claude, `requirements-anthropic-sdk.txt` pins anthropic2.8.0 and httpx2 2.16.0. An authorized user can install official PyPI packages into a separate environment with `python -m pip install -r requirements-anthropic-sdk.txt`; validation used a separate project-isolated environment, not global packages. This is a top-level version pin, not a complete transitive hash lock. Runtime records dependency versions and SDK source hashes. An isolated Anthropic2.8.0/httpx2 2.16.0 environment now passed one actual-SDK synthetic-key request through mocked HTTP (Slurm1121725). Network was blocked during that check; no live Anthropic API or account capability was tested. Earlier boundary tests additionally fake the SDK interface.

Claude accepts one ANTHROPIC_API_KEY assignment in an owner-only regular file, with no symlinks or expansion; OpenAI retains its secure loader. No environment/profile credential fallback is allowed. The key passes only through isolated worker input, never plans or command arguments. Offline tests use synthetic keys.

## Data and invocation

Use README commands. `--prepare-datasets DIRECTORY --write-spec NEW.json` creates a fresh registration for the same four IDs/manifest without altering data. Live mode requires the original server directory, manifest `d2c880f50dad90ce0593ce03c44e0650a1b7231d89c2ba71c6a529c4cc13af44`, and one repetition. `--demo` uses the byte-preserved fixture duplicate. Cases are fragmented_gap feasible/negative and eligibility_budget feasible/negative. Arbitrary cohorts remain disabled.

Baseline never dispatches a solver. Assisted validates the model-authored instance with temporal strict v2 and invokes CheckedSolver/MergedSolver, recording its digest. Status/schedule/certificate from the checked result are independently scored against the original instance. A wrong translation can fail despite a valid translated schedule. There is no second model call or promotion of UNKNOWN.

The retained Claude CLI entry is `tools/run_paired.py --datasets SPEC --config CONFIG --out NEW_DIRECTORY --allow-live`, with an explicit legacy adapter configuration from the paired guide. Historical prompts/results are unchanged; CLI is not API fallback.

## Bounds, accounting and assessment

Exact-field settings retain maxima: eight planned API calls, four solver invocations, one worker/repetition; 2,000 output tokens including reasoning; 7,500 serialized request bytes plus 256-token planning allowance; 20-second call/local worker deadline; 45-second/12,000-token post-return attempt allocation; solver 100,000 nodes/two seconds. Live profiles explicitly select gpt-6-astra or claude-opus-5-5, high effort. Settings remain provisional.

Rates are USD per million tokens: input, output, cache_read, cache_write_short, cache_write_long, with source identity. Claude short/long writes mean five minutes/one hour; OpenAI means 30 minutes/12 hours. Claude input excludes cached reads/writes; OpenAI input includes them. Reasoning is included in output, never charged twice. See [Claude cache semantics](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). Unknown counters, unsupported returned tier/speed/geography or missing usage retain unknown cost and stop scheduling. Standard is required: OpenAI default, Claude standard.

Request reserve uses serialized bytes plus 256, maximum configured input/write rate and full output allowance; actual SDK wire size/reserve is checked before dispatch. Whole-plan reserve must fit the configured ceiling. Estimates are not billing or guaranteed hard caps. Local child termination does not guarantee remote cancellation. Attempt limits are post-return/cooperative checks, not rollback.

`plan.json` pins data, prompts, sources, settings and SDK identities. `attempts.jsonl` retains raw response, model text, usage, translation digest, solver result and original-instance verdict. `summary.json` retains all eight slots and unknown costs for missing attempts. `--assess` checks joins and source/data identities without provider or solver execution. FEASIBLE, certified INFEASIBLE, model/solver UNKNOWN and format/translation/solver/provider failures remain distinct. Optimality is not implemented.


## Source integration on 12 November 2026

The 26 additive PR26 files were imported from verified merged-main source a8621d202d2b14480724eecfeef4741969d110f4 (tree 3bf8cc5b5cd2b9e16e970395e6fa8b2a8801918b). All 275 upstream blobs were verified against base 33a53ec plus the transferred additions; local README/contribution changes are explicit exceptions. This is source integration, not a Git ancestry merge. Historical OR-Tools code/results remain byte-preserved and separate from this direct protocol. Its default eight workers/ten seconds and extra result fields do not satisfy CheckedSolver; the direct backend remains DFS with 100,000 nodes/two seconds. No implicit backend switch occurred.

The imported report's identical-prompt and solver-causes-improvement statements are team claims, not established by this integration review: arm prompts differ, historical rerun/provider-limit conditions differ, and selected comparisons are not controlled causal evidence. Historical text and scores are preserved rather than rewritten.


## Verified smoke check

On 12 November 2026, official OpenAI SDK 3.46.0 called gpt-6-astra/high with explicit Standard service on the four registered original-synthetic development cases, both arms once. All eight responses were completed and returned the requested model and Standard tier. Each arm produced two independently valid FEASIBLE schedules and two supported INFEASIBLE certificates. All four assisted translations passed strict schema validation before Python invoked checked DFS. There were eight model calls, four DFS calls, zero post-solver model calls, and no retries or repairs. Saved offline reassessment matched.

The run used 1,700 maximum output tokens per call, not the template's 2,000. At the pinned Standard rates, conservative reserves were US$0.198125 maximum per call and US$1.5202 for the plan, within US$0.20/US$2.50 guards. The 2,000-token preflight was retained as a failed preflight, with no calls. Actual reported usage was 6,870 input tokens and 2,018 output tokens including 651 reasoning tokens; cache reads/writes were zero. The usage-based estimate was US$0.16960 (US$0.05826 baseline; US$0.11134 assisted), not verified billing or a guaranteed cap. No missing slots, UNKNOWNs, format/evidence failures, refusals, incompletes, timeouts or budget violations were recorded.

Server-local immutable evidence: `/home/t/tehxa/cs3263-review/direct-main-integration-20261112-clJYclQa/live-direct-smoke/` contains plan.json, attempts.jsonl and summary.json. The parent directory contains LIVE-RESULTS.json, LIVE-RESULTS.md and live-saved-assessment.txt. Run ID: `58815ac97379d42443302225cbe8126fad43d74de8ad87a07cbb543ddd46f142`; Slurm 1122269 completed successfully. These paths are server locations, not download attachments.

This validates the recorded pipeline only on four reused development cases. It is not a holdout evaluation, general accuracy or superiority claim, and is not pooled with earlier protocols. No optimality objective or OR-Tools substitution was added. Live Anthropic behavior remains unvalidated; its actual installed SDK passed a synthetic-key/mock-HTTP check only. Full legacy-suite verification remains incomplete after the earlier partition timeout; no denied repartition was repeated. The source and receipt hashes captured for the live run are preserved; later documentation corrections are recorded separately.


### Saved-assessment correction after the smoke

A later offline review reproduced a saved-record validation gap: deleting model/final outputs could bypass conditional joins while stored success flags remained true. Assessor revision `direct-saved-evidence-joins-v2` rejects missing evidence/fields and requires eligible raw-response/model joins; legitimate failed outputs remain in planned denominators. This does not change model requests, translation, solver dispatch or intended-instance scoring. It is an offline-verified assessor correction, not another live run.

The successful smoke used the frozen `direct_benchmark.py` SHA256 `8ea916477d39f3e165e1a891ad654e23bd780715ff53ed108d13a342e589ae84`; that source and all original receipts remain preserved server-side. Strict source pinning is unchanged: assessing an old plan with changed source is rejected. Replay requires the recorded matching source. A separately recorded read-only recheck applies the stronger evidence joins to the saved smoke receipts, without rewriting their plan, source hashes, outputs or scores.
