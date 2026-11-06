# Draft v2 input view: no fixed-ID certificate example

User direction: ordinary inputs must not give misleading examples with absent IDs.
Version `tier-a-shared-input-view-draft-v2` preserves every existing file/version.
This is input standardization only, not team output/interface/protocol acceptance.

`tier_a_input_view.prepare(directory, arm, wrapper_version)` reuses the old audited,
hash-pinned preparation, then derives exactly nine eligible development inputs in
stored order. Six oracle-only negatives remain validation-only. No provider/tool
schema/runner is supplied. Existing solver/scorer and intended-instance checks stay
unchanged. All cases here are development-visible, not future held-out examples.

Exactly one required literal raw span is replaced, or preparation fails:

    For an infeasible decision, a supported certificate is {"kind":"pair_order_impossible","patients":["A","E"]}: two mandatory surgeries

Derived span:

    For an infeasible decision, use a certificate object with exactly keys "kind" and "patients". The kind must be "pair_order_impossible" and patients must be a list of two distinct actual mandatory surgery IDs from this instance. The two mandatory surgeries

The remainder, including forced-sharing/both-orders/relaxed-proof semantics and
all instance primitive fields, is unchanged. No actual certificate, label or gold
IDs are supplied. Raw text remains immutable; derived text is a new prompt view,
not the original prompt. Reverse replacement is tested to recover the original
exactly. Missing/duplicate raw spans reject; malformed examples appear only in
explicit unit tests, not ordinary model inputs.

Common shared wrapper, identical for both arms:

    Solve the following controlled instance under its hard constraints and JSON answer shapes. Optional surgeries may be omitted; there is no optimization objective. FEASIBLE requires a valid schedule. INFEASIBLE requires a supported pair_order_impossible certificate; otherwise return UNKNOWN. Use actual instance surgery IDs in evidence. Priority and emergency are metadata only.

Order: shared_instruction; arm_instruction (unchanged v1 direct or conditional-CSP
draft); derived instance_text. These are the ONLY model-facing fields. Message
roles and tool exposure remain team decisions. The CSP interface must be agreed
before use; the conditional instruction does not establish one.

`bindings` returns evaluator-only version, transformation hash over compact JSON
[raw_span,derived_span], raw/derived UTF-8 text hashes, shared/arm hashes and common
hash over compact JSON [shared_instruction,derived_text] with ensure_ascii=False.
Do not attach these receipts, raw text, readable case IDs, families, gold, eligibility,
lineage, inventory or run metadata to model payloads. Necessary patient/resource IDs
inside the intended text remain permitted. Module/source hashes must also be recorded
in any later reviewed consumer. No receipt implementation is an access-control boundary;
caller isolation/no concurrent source mutation remain assumptions of this offline helper.

Tests cover exact one-span transform/reversal, absence of fixed example/disclaimer,
identical common content/hashes across arms, raw-versus-derived identities, deterministic
order, unsupported versions/arms/drift and unchanged original bytes. No model behavior
or new solver interface was tested. Old v1 is retained for reproducibility, but normal
new prompt proposals should use v2. Team adoption, schema/tool exposure, roles and
actual execution policy remain separate decisions; publication is not authorized.
