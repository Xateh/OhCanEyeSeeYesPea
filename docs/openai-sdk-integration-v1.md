# Official OpenAI SDK integration v2 (review repair)

This additive SDK path replaces the network transport for future approved use. Historical raw-HTTP modules, prompts, plans and results remain unchanged and assessable. No SDK live call has been made. SDK v2 is the current offline-reviewed integration. SDK v2 repairs partial-read retention, streaming timeout classification and explicit encoding rejection.

## Contract

Use responses_sdk_runner.py and tools/run_responses_sdk.py. The protocol remains AI without CSP versus a mandatory AI-plus-CSP workflow: a tool-free baseline final, or model-authored text-JSON translation, exactly one checked local invocation, then a second model final. Native API tools stay empty. Final schema and independent intended-original-instance feasibility/evidence scoring are unchanged. UNKNOWN is an abstention, not a proof or a fabricated success. Optimality is not implemented.

This like-for-like revision deliberately retains the current four-case calibration registration and one-repetition/one-invocation guard, gpt-6-astra/high Standard profile and existing source pins. It does not silently authorize broader corpora or another experiment. The published generic dataset/paired framework remains available separately; a broader SDK cohort requires an explicitly reviewed registration revision.

## Dependencies and setup

Official package: openai==3.46.0, with 14 resolved distributions in total (SDK plus 13 dependencies) pinned and wheel hashes in requirements-openai-sdk.lock. SDK documentation requires Python >=3.10; this wheel lock and validation are specifically CPython3.12/Linux x86_64 on xlogin. Other Python/platform combinations require a separately reviewed wheel lock, not an automatic upgrade. No system packages were changed.

From the project root, an isolated optional environment can be prepared with:

```sh
python3 -m venv --without-pip .venv
python3 -m pip --isolated --python .venv/bin/python install --index-url https://pypi.org/simple --only-binary=:all: --require-hashes -r requirements-openai-sdk.lock
```

The final clean-copy environment for this revision is CPython 3.12/Linux x86_64, installed from the hash lock. Offline SDK tests use synthetic keys and httpx2.MockTransport only. The baseline matrix keeps SDK optional; a dedicated CPython 3.12/Linux job installs the hash lock, requires SDK imports, and executes SDK regressions normally and under -O. Local clean-copy validation is separate from actual GitHub CI, which must be checked for the exact published head.

## Configuration and invocation

Generate the SDK binding in the same pinned environment using responses_sdk_transport.binding; use responses_sdk_runner.VERSION and the new adapter revision. The exact existing registered four-case specs may be reused. Never relabel an old plan or alter its source hashes. sdk-settings.example.json is key-free and leaves the intended-spend ceiling null, so it fails closed until deliberately configured and authorized.

```sh
.venv/bin/python tools/run_responses_sdk.py --datasets DATASETS.json --config SETTINGS.json --out NEW_DIRECTORY --allow-live --allow-key-file --key-file .env
```

This command is an interface example, not permission to run. Both explicit flags and separate account/key-use/spending authorization are required. The existing bounded owner-only .env loader is reused; no SDK/environment fallback obtains keys. Never put a key in arguments, results or source control. An existing output directory is refused. No automatic retry or replacement is performed.

## SDK behavior and limits

Official OpenAI.responses.with_streaming_response.create performs the request. stream:false remains the API body setting; streaming-response here controls bounded local HTTP-body reading, not an SSE protocol change. SDK retries=0 and HTTP transport retries=0; redirects and proxy/environment routing are disabled. Request JSON fields/values equal the legacy transport; SDK-specific HTTP headers and JSON key ordering may differ. Wire body size/hash are recorded; request strings are unchanged.

A clean-environment child prevents SDK ambient custom headers, keys, organization/project or routing settings from influencing the call. The key goes only through an in-memory stdin pipe to the official SDK, never an argument, environment value or file. Logs and raw SDK error diagnostics are suppressed. The child has a local wall timeout as well as explicit SDK socket phase timeouts. Killing it cannot guarantee remote cancellation or a billing cap. Unknown cost/outcomes remain unknown and stop further scheduling.

Raw provider bytes/text remain authoritative. Typed model_dump(exclude_unset=True) is compared diagnostically, never used to repair/coerce scored outputs. API status errors retain bounded raw bodies and usage where available. Encoded unsupported bodies are retained bounded without automatic decompression and fail closed. The same per-call/attempt/whole-plan guards, cache/read/write/reasoning inclusion, returned-tier validation and receipt accounting remain.

## Evidence and review

See the SDK migration evidence directory for full source/test review packet, transport/runner diffs, official-wheel install report, parity records, test commands and preservation hashes. All SDK calls were mocked; synthetic receipts are not model results. AI assistance authored code/tests/docs. The coordinating code review is complete; this is not independent human/team sign-off. Future live SDK validation remains pending. The implementation and repair phases made no commit, push or PR edit; publication follows as a separate authorized step.

Official references: https://developers.openai.com/api/reference/python and https://github.com/openai/openai-python .

## Repair boundaries and portable tests

SDK v2 retains bounded bytes/status/safe headers when a response stream raises. Timeout and non-timeout read failures are recorded separately; incomplete bodies are never parsed/scored and usage/cost stay unknown. Unsupported encoding is explicitly rejected even if its raw bytes happen to be valid JSON. A hard local child termination can lose in-child bytes not yet delivered to the parent; the parent keeps the request/timeout and unknown remote outcome, without retry or fabricated cost. No remote-cancellation guarantee is made.

fixtures/responses-offline-v1 holds the original small synthetic package byte-for-byte plus minimal non-secret regression projections. tests/responses_fixture.py binds paths only inside the test process; production four-case guards and original history remain unchanged. The offline harness blocks network and external xlogin pilot reads. No held-out dataset was opened, no new experimental cases were generated and no historical scores were rewritten.
