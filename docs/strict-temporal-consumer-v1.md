# Strict temporal offline consumer v1

This local follow-up explicitly adopts `temporal-strict-validation-v2`; it does not modify PR23, SDK calibration, frozen corpora or old plans. `strict_benchmark_v1.py` reuses `paired_runner` execution, accounting, bounded receipt retention and checked-solver interfaces. It provides no live transport, credential loader or arbitrary-cohort CLI.

## Exact registration

The fixed frozen Tier A source has 15 cases: seven feasible, two pair-certified infeasible and six oracle-only infeasible. The new validation registration selects the `optional-omitted`, `optional-forced` and `fragmented-3` cases plus a separately identified malformed empty-mapping schema probe. These are development/software-validation fixtures, not a new study split or corpus admissions. Original source membership and nine-case research eligibility are unchanged. The source's six oracle-only cases are still audited; the selected oracle-only case stays in this consumer's planned denominator.

Four entries times two arms times one repetition yield eight planned slots. All four entries retain their original-instance hash and input status. The invalid probe emits no model text and executes neither arm; both slots remain explicit input rejections. The six valid slots remain eligible for execution or missing-slot accounting. `missing` includes every unexecuted slot; `input_invalid` separates rejected inputs, while `valid_missing` identifies interrupted/unattempted valid slots.

The plan pins source files (including strict v2, frozen semantic checker/text/solver/oracle, paired execution/accounting and CLI), fixture hashes, selected/full-source IDs, text hashes, original/normalized-instance hashes, strata, seed/order, settings and attempt identities. Selection is fixed and start arms alternate across the four entries; the invalid probe is still preflight-rejected. Seed zero does not seed model generation. The plan and output directory cannot be overwritten; assessment rebuilds registration and refuses source, fixture, plan, case or attempt drift.

## Boundary and treatment

Registration performs strict structural/semantic validation, non-mutating normalization and canonical text generation. The existing actual-ID instruction view is explicitly derived; reversing that one pinned instruction span for the controlled parser must recover the normalized intended instance. Neither gold labels, witnesses, eligibility/lineage nor routing IDs enter provider messages. Actual surgery/resource IDs remain legitimate problem text. Both arms receive identical case text and existing shared/arm instructions.

No-tools dispatch is disabled. CSP requires one model-authored schema-1.1 translation and one checked invocation, then a model final; an early direct final is an operational failure and repeated invocation is blocked. Strict v2 validates the actual translated arguments, never substitutes the intended instance, and independently scores the final against the original intended instance. Frozen strict JSON/output-shape checks remain separate from semantic evidence validity. No native API tools or SDK protocol is introduced here.

The default provider is the existing deterministic controlled-text fixture translator, not an LLM. Its no-tools answers deliberately abstain; CSP copies checked results. Test fixtures can supply known finals or faults to exercise scoring. Their zero-usage records explicitly mean no model execution, not measured model efficiency. A provider plug-in assertion is not a sandbox against malicious same-process code.

## Commands (offline only)

From the repository root, choose a nonexistent output path:

```bash
python3 tools/run_strict_benchmark.py --out /path/to/new-offline-output
python3 tools/run_strict_benchmark.py --assess /path/to/new-offline-output
python3 tools/run_offline_suite.py test_strict_benchmark_v1.py
python3 -O tools/run_offline_suite.py test_strict_benchmark_v1.py
```

The returned rows distinguish input-schema rejection, valid final evidence, oracle-only/solver UNKNOWN, final UNKNOWN, translation errors, format errors, semantic errors, provider/solver failures, timeouts, missing usage and valid missing slots. Saved assessment uses plan/receipts rather than trusting the saved summary. Duplicate or unplanned receipts are rejected. UNKNOWN is not a certificate or success; unsupported objective claims do not expand the final contract.

Operational fixture allocations retain one worker, 100,000 nodes/two solver seconds, at most one invocation, two provider callbacks per CSP attempt, no retries, 12,000 attempt tokens and 45 seconds. The fixture-only USD1 scheduling ceiling is not permission for paid use. Unknown cost stops new slots. Provider/plugin timing remains cooperative/post-return; this is not a hard cancellation or billing guarantee. There is no API authentication path in this consumer.

## Optimality and next adoption decision

Optimality is explicitly not applicable. The authoritative shared instruction in `tier_a_input_view.SHARED` says no optimization objective; priority/emergency are metadata and optional work may be omitted. The frozen oracle enumerates mandatory-only feasibility. The team must define objective function/direction, optional-job handling, weights/units, ties/tolerance and a verified optimum/reference bound before an optimality extension. A model objective claim or UNKNOWN is not such a reference.

This completes local consumer adoption of strict v2 for the fixed offline validation cohort. Moving the boundary into a broader benchmark registration or live SDK protocol requires an explicit versioned integration/review; it is not silently enabled here. No experiment or publication is authorized by these commands or defaults.
