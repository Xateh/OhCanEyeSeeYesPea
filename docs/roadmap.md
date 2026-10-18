# Research roadmap and review gates

The current delivery is the original-synthetic offline pilot in [draft PR #1](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/1), not completion of the project. The [issue tracker](https://github.com/Xateh/OhCanEyeSeeYesPea/issues) is the actionable work list; this guide explains ordering and ownership boundaries.

## Delivered baseline

- 48 cases/24 paired families, controlled text, separate gold, lineage/hashes and family-disjoint splits
- Temporal schema, independent witness/proof checks, tiny-case Cartesian oracle, bounded DFS and paired mock harness
- 74 test methods and offline regeneration/96-arm integration verification
- PR CI for Python 3.10–3.14; baseline PR run for head `38c34bbb` passed using GitHub's PR merge checkout

These do not establish broad difficulty, clinical adequacy, real-model performance, final team acceptance or an OR-Tools implementation.

## Ordered remaining work

1. **Agree scope and interfaces.** Confirm final formulation and research question, prompting comparison, team ownership boundaries and acceptance criteria. Review the pilot before any merge.
2. **Prepare the research foundation.** Expand original-synthetic coverage/difficulty with independently checked labels and family holdouts. Resolve rights before using/releasing source-derived data. Agree and implement Allan's solver interface, while keeping independent validation.
3. **Freeze the experiment.** Benjamin/team defines prompts, conditions, repetitions, metrics and matched budgets; Xu An's benchmark tooling exposes reproducible configuration and aggregation. Select a provider only through team decision and authorize data/spend before live calls.
4. **Run and analyse real pairs.** Start with a bounded approved pilot; freeze versions, preserve failures and compare intended-instance validity, infeasible decisions/certificates, UNKNOWN, violations, runtime and known token usage. Use family-aware interpretation and report limitations.
5. **Integrate the final deliverables.** RAI documentation can start now; incorporate actual failure findings later. Prepare the report, presentation, reproducibility pack and team review. Optional wheel support is separate from core checkout-based research.

## Actionable issue index

- [#2: Agree final research scope and team interface boundaries](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/2)
- [#3: Design and validate broader dataset coverage and difficulty](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/3)
- [#4: Resolve source-derived data licensing and release boundaries](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/4)
- [#5: Agree and implement the OR-Tools solver adapter contract](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/5)
- [#6: Extend independent validation and adversarial regression coverage](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/6)
- [#7: Freeze prompting conditions and matched evaluation protocol](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/7)
- [#8: Implement and contract-test an approved real-model provider](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/8)
- [#9: Add reproducible experiment configuration and result aggregation](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/9)
- [#10: Run the approved paired real-model study](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/10)
- [#11: Analyse paired outcomes and translation failure modes](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/11)
- [#12: Document Responsible AI assumptions and human-review limits](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/12)
- [#13: Prepare reproducible report and presentation handoff](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/13)
- [#14: Validate optional wheel packaging or document checkout-only support](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/14)

All issues have acceptance checklists and dependencies. Conditional source-data licensing and optional wheel packaging are distinguished from core experiment blockers. No issues are automatically assigned.

## Team boundaries

The [original proposal and progress](https://docs.google.com/document/d/1A1CfuLvvGqqFIVxMyThe0pkc4jgBMG6oruXJizW-Nsw/edit) records:
- Xu An: problem/dataset investigation; later expanded to benchmark tooling
- Allan: OR-Tools framework
- Benjamin: prompting, experiments/results analysis and Responsible AI
- Everyone: whole-project review

Issue role suggestions describe these interfaces, not confirmed new assignments. Final scope and integration need explicit team agreement. Do not shift all solver/experiment/RAI tasks onto Xu An or assign GitHub users based on names alone.

## Schedule and decision boundaries

Planning records state presentation in the **week of 9 November 2026**, with exact slot/format unconfirmed, and report due **13 November 2026**, with clock time unspecified. Confirm current official instructions before scheduling submission. Dates from the September proposal are historical targets, not proof that milestones were met or current commitments.

Documentation and issue creation do not authorize merging, choosing a paid provider, running paid experiments, redistributing restricted data, public release or course submission. Those remain separate decisions.

## Completion evidence

An issue is complete only when its acceptance checklist has evidence: reviewed artifacts/commits, passing checks for the exact version, measured results where required and recorded team decisions. Do not close real-experiment tasks using mock outputs, dataset tasks using only count increases or integration tasks using an unreviewed contract.
