# Original-synthetic Tier A v1 review corpus

This separate 15-case hand-designed review corpus builds on reviewed stack
`e3f9dbe19381a43bd39c64343ce32966d15dce9e`. It preserves the original 48-case pilot
and all existing generator, checker, oracle, solver, evidence and provenance bytes.
Its version is `tier-a-original-synthetic-v1`; destination is
`fixtures/tier-a-original-synthetic-v1`. It is neither a clinical dataset nor a
real-model evaluation. The cases reuse analytical regression constructions; the
count does not establish novelty, difficulty, generalization or broad coverage.

## Build and audit

From a clean checkout with standard-library Python only:

```bash
timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -m surgerybench.tier_a_dataset NEW_DIRECTORY
timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -m surgerybench.tier_a_audit NEW_DIRECTORY
timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
timeout 60s env PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s tests -q
```

The builder refuses any existing destination, including an empty directory. It
validates every case before creating its destination. A disk write failure may
leave a partial new directory; it is never treated as audited evidence and the
builder will refuse to overwrite it. The read-only auditor rejects partial or
unexpected contents. There is no resume/retry overwrite mode.

`tier-a-model.jsonl` contains only `case_id` and controlled-language `text`.
`tier-a-gold.jsonl` contains privileged instances, authored labels, arithmetic
anchors, hand-authored witnesses, optional-present witness where supplied,
oracle receipts, certification category, coverage tags and source/code lineage.
`coverage.json` is the per-case coverage/label/certification ledger.
`manifest.json` hashes the other three files. Case IDs include an instance digest;
no random seed, wall-clock timestamp or machine path affects content. Lineage pins
the reviewed base and SHA-256 of all scheduling-package Python sources, including
the separate builder/auditor. Same source bytes produce byte-identical files.
Hashes detect corruption, not malicious authorship or independent authenticity.

## Evidence and separation

Labels come from explicit arithmetic in `cases()`, never DFS output. The builder
requires a complete independent Cartesian-oracle result agreeing with that label
and checks all returned feasible witnesses against the intended-instance checker.
The auditor imports neither the builder nor DFS: it recomputes schema/envelope,
text/instance integrity, complete oracle result and exact receipt, checks stored
and recomputed witnesses, and validates existing compact certificates. Human
review of the retained arithmetic remains necessary; the audit does not prove
natural-language arithmetic statements. Oracle and checker are the unchanged
pilot implementations; this is not a new independent oracle implementation.

Negative labels have two evidence categories:

- `pair_order_impossible`: the existing independently checked compact certificate
  proves a contradiction even with gaps/calendars/budgets relaxed.
- `oracle_only`: complete tiny enumeration proves internal gold infeasibility;
  `certificate` is null. No model-facing compact proof is claimed. Existing DFS
  may legitimately return exhausted UNKNOWN on these cases.

Feasible cases have `not_applicable` certification and a checked authored witness.
Incomplete oracle outcomes are rejected before export; no unresolved case is
silently labelled. Optional jobs retain the existing existential interpretation:
omitting optional load can establish mandatory feasibility. The oracle does not
enumerate every optional-present schedule or establish throughput/optimization.
The optional-adjacent case also stores a checked optional-present witness.

This format is deliberately **not compatible with the old paired harness**:
`case_id` replaces its required `id`, filenames/version differ, and the manifest
sets `old_harness_compatible` to false. A regression verifies fail-closed rejection
before provider construction/output. Do not rename fields or feed oracle-only
negatives to the old harness as certified results. A future consumer needs a
separate evidence/scoring contract.

## Coverage, split and resource limits

Isolated effects precede interactions in the ledger: positive room gap (feasible
and infeasible boundary), positive surgeon gap, fragmented-room duration pair,
calendar intersection, optional/mandatory load pair, optional adjacency, room
budget, eligibility/budget pair, eligibility/calendar pair, and a deadline pair
contradiction with extra gap. This is 15 cases in 10 hand-designed families.
Some tags and effects overlap. These are not independent samples.

Every case is `provisional_review`, and every relative stays in that same split.
There is no train/validation/test holdout or independence claim, including with
the original pilot and earlier analytical tests. Team approval is needed before
defining research splits or using the cases in a model evaluation.

One CPU worker; at most 24 cases; each case has one day, 1–2 jobs/rooms/surgeons,
duration/deadline/calendar endpoints/gaps/budgets at most 10, at most two windows
per resource/day. Domain-product upper bounds, computed before enumeration,
must be at most 100, below oracle limit 10,000. Oracle preprocessing still scans
up to 1,440 start minutes per job/eligible room, bounded by the job/resource cap.
At most 100 solutions are possible. The current 15 cases have maximum product
bound 36. Every focused build/audit/test command has a 60-second shell cap; do not
automatically enlarge the envelope. Files are capped at 1 MiB each for audit.

Regression tests cover deterministic bytes, overwrite refusal, manifest/text/
label/witness/receipt/lineage corruption, false certificates, resource envelope,
old-harness rejection, separation and original fixture identity. Existing Tier A
tests retain precise DFS UNKNOWN versus compact-certificate boundaries.

## Next decision

Review these 15 cases, arithmetic anchors, evidence categories and provisional
coverage ledger before accepting this corpus. Decide whether oracle-only negatives
remain validation-only or need a new independently checked proof/scoring contract.
There is no automatic corpus scaling, real provider integration, publication or
commit/push authorization in this slice. Team acceptance, OR-Tools interface and
evaluation protocol remain open.
