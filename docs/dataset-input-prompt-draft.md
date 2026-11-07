# Draft dataset-to-model input standardization

Scope refinement: dataset ownership includes standardizing the dataset inputs and
proposing shared instructions. General experiment configuration/aggregation under
issue #9 is outside this increment. This is NOT accepted prompting/protocol policy.
Based on main 3f20017148b3290c518483b60afc7c4a75971a9e and its team-agreed scoring
freeze. PR20 prompt-hash preparation is separate; it selects no prompt content and
is not incorporated here. No provider, tool schema, model call or runner exists here.

## Exact proposed payload and ordering

`tier_a_inputs.prepare(directory, arm, wrapper_version)` accepts ONLY the frozen
15-case Tier A package through the existing independent audit and exact pinned
export identities. Explicit version is `tier-a-shared-input-draft-v1`; arms are
`no_tools` and `csp`. Return order follows stored model/gold order, selecting the
nine evidence-eligible development cases only. Six oracle-only negatives never
enter this input list. This does not choose a real experiment corpus or authorize
execution. Other corpus versions/arm values/wrapper versions fail closed.

Each returned item has ONLY three string fields. Proposed assembly order:
1. shared_instruction, exactly the module's SHARED string;
2. arm_instruction, exactly the corresponding ARM string;
3. instance_text, the ORIGINAL frozen controlled text, byte-identical as UTF-8.
No provider message-role serialization is selected here; the eventual adapter must
preserve this order/content and document roles before use. Input items are fresh
objects. There are no few-shot demonstrations, family headers or extra case labels.

The shared instruction and instance text are identical across arms. The only
proposed arm difference is direct/no-tools versus translating into a separately
approved CSP interface if supplied. Actual tool exposure, arguments/results schema,
solver-status/proof mapping and availability are separate team decisions. The CSP
instruction is a draft boundary, not an assertion that an approved interface exists.
Do not run the CSP arm without resolving that interface; no tool is attached here.

## Shared semantics retained from frozen controlled text

Integer minutes; zero-based days; within-day start but absolute release/due from
day0. Completion=start+duration must meet due; start>=release. Each mandatory job
exactly once, each optional job at most once and freely omitted. No throughput,
priority, emergency or soft objective. Nonpreemptive whole interval in one eligible
room with its fixed surgeon; half-open intervals, one uninterrupted availability
window on BOTH resources. No room/surgeon overlap; gap applies between consecutive
uses of that resource; daily surgery-minute budget sums durations, not idle/gap time.
A schedule on a mistranslation is not success on the original instance.

FEASIBLE needs intended-instance-valid schedule rows (patient/day/start/room), not
a copy of gold witness. INFEASIBLE needs supported pair_order_impossible evidence
for two distinct actual mandatory IDs forced to share a surgeon or same singleton
room, with both relaxed orders impossible. No timeout, exhaustive solver claim,
empty schedule or oracle-only arithmetic is silently a supported certificate.
Otherwise UNKNOWN. Existing frozen output schema/checker remain authoritative;
this module does not add output keys or implement an output normalizer.

## Versioned clarification, no retroactive text edit

The shared wrapper explicitly clarifies that the frozen literal A/E certificate
example is illustrative: use actual mandatory IDs only when both orders are
impossible. This is a NEW PROPOSED instruction version and changes effective prompt
content, identically across arms. It is not the old prompt and must be recorded as
such; original text files and renderer remain unchanged. Team review must choose
whether to adopt it. Any future renderer/text change needs its own corpus/text
version and explicit registration, not rewriting frozen exports. No hidden answer
or certificate is supplied by the clarification.

## Privileged-data boundary and identity

Never add readable case IDs, family/tags, labels, eligibility/certification classes,
lineage, gold instances/witnesses/proofs/arithmetic/oracle receipts, run IDs, hashes,
usage/budget receipts or this inventory to model content. Patient/resource IDs in
the actual instance are necessary task data and are permitted. Hashes/joins stay
runner/evaluator-side. Gold may validate package offline but never repair model
translation or enter tool-visible arguments. Input selection by evidence category
must be disclosed in methods; selection is not itself a prompt feature.

`fingerprint(payload)` returns SEPARATE evaluator metadata: wrapper version,
UTF-8 SHA256 of shared instruction, exact text, arm instruction, and a common hash
of compact JSON [shared_instruction,instance_text] with ensure_ascii=False. This
binds common bytes across arms. Record module/source and corpus export hashes too.
The fingerprint is identity, not a validator that arbitrary caller-supplied text
came from the corpus; only prepare performs package admission. Do not append hashes
or wrapper version to prompts. Tests assert allowed fields and specific leakage
sentinels; they do not establish access control against an arbitrary malicious caller.
Caller isolation and no concurrent corpus mutation are assumed for this offline helper.

## Before use

Team must review exact SHARED/ARM strings and certificate clarification; decide
message roles/serialization, output/CSP schema and tool exposure with interface
owner, and freeze prompting/protocol/model/budgets independently. Existing scoring
and planned denominators are preserved. Future holdout text must never be used to
tune this draft; all current cases are development-visible. No new holdout is read,
authored or exposed here. Publication/execution need separate approval.
