# Paired development runner implementation plan

Goal: reuse the existing datasets and frozen scoring in a provider-injectable offline paired runner, with a small solver integration contract and an accurate contribution record.

Architecture: version-specific dataset preflight produces evaluator-only intended instances plus shared model text. A new runner passes only public messages/tool definitions to providers; a checked solver receives only model-translated schema1.1 arguments. Frozen output_verdict scores final raw/normalized evidence on intended instances. Existing generator/auditor/registration code is reused; no solver is rebuilt.

Constraints: xlogin only; standard library; one worker and60-second verification commands; no installs/live calls/publication; preserve accepted v2/v3 exports, main fixtures/results/scoring and all original worktrees. Keep failures and missing usage in explicit plans. New configuration is software preparation,not a team research protocol.

1. Inventory/reconcile main63b8f4b and preserve38 unpublished additive files. Correct the demonstrated legacy auditor HEAD-portability defect with an explicit exact-source compatibility registry; test legacy manifests and source-drift rejection.
2. Add benchmark_datasets.py plus portable hard_corpus_registration.py. Load Tier A eligible9, registered v2,v3 and Allan tool-supported51 using their existing checkers/preflight. Require explicit selected IDs/package identities. No regeneration or mixing of datasets by default.
3. Add solver_interface.py: CheckedSolver(plugin,limits), invoke(translated_arguments), with schema/version/bound checks and checked evidence. Reuse CSPAdapter; map malformed/unsupported/timeout results to UNKNOWN plus diagnostics. Test wrong translations against external intended-instance scoring.
4. Add paired_runner.py: strict explicit configuration, deterministic planned slots/order/seed, provider.respond(messages,tools,limits), per-attempt receipts, original raw finals, usage coverage and immutable run directories. Save plan before providers,append failures,retain missing slots on interruption; summaries use fixed denominators and paired evidence success/completion separately. No retries or silent replacement.
5. Focused tests cover selected old/new corpus boundaries, role/text equality/gold isolation, valid alternate witnesses and optional omission, malformed/unsupported solver/provider replies,timeout/UNKNOWN/usage gaps, planned missingness and duplicate rejection. Add integration examples and CONTRIBUTIONS_XU_AN.md with AI declaration and explicit reused team work.
6. Run focused/full normal and-O offline checks on the final combined tree; verify hashes of main fixtures/results/contracts and all old artifacts. Review actual diff and save separate receipts/patch. Leave changes uncommitted and report remaining protocol decisions.

Execution: inline in this existing task; no agents,sessions,commits or remote publication. Historical64/100 first attempts and38/40 separate reruns stay intact and are not new results.
