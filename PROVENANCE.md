# Pilot provenance

Base repository: `https://github.com/Xateh/OhCanEyeSeeYesPea`

Actual cloned main commit: `d0be540314afdd28d3e10d3a509a8129b9c8c521`.
The base has one README and its original history. The review branch adds files
without changing the README. It is published as `feat/arrival-deadline-pilot` in
the private repository with [draft PR #1](https://github.com/Xateh/OhCanEyeSeeYesPea/pull/1).
Historical local-only evidence describes the pre-publication validation stage.

## Included by explicit allowlist

- Original `surgerybench/checker.py` and package version, six `temporal_*.py`
  modules, and temporal regression tests from the approved standalone pilot.
- `common.py`: the existing standard-library serialization/hash/JSONL helpers
  extracted to avoid importing the larger corpus generator or original harness.
  Initial packaging changed only imports in `temporal_dataset.py` and
  `temporal_benchmark.py`. The focused follow-up also tightens model-revision
  validation and incomplete-usage accounting in the latter.
- All four files of the approved original-synthetic arrival/deadline pilot:
  model text, separate gold, summary and hash manifest.
- New package-only and focused original-synthetic regression tests, offline
  verification script, concise instructions,
  ignore rules, existing original-code/synthetic-data license and package metadata.
- Sanitized original validation summary and original source hashes, plus the new
  package verification summary. No raw provider transcripts or terminal logs.

Fixture manifest SHA-256:
`00f371ff5570ddf2e93983c1ccabe953882d8c93dfc74510a0a8e8c87d848812`.
Original generator module-set revision:
`e574b76347d76deb5fb1dda2bced0f79a03479bd56a4c54d760351f808001289`.
Source hashes identify the pre-packaging implementation. References to excluded
source filenames in that hash inventory are hashes only, not those files.

All 48 gold records were checked before transfer for `source.kind` equal to
`original_synthetic`, schema 1.1 and expected count. Their manifests and semantic
provenance are independently checked again in this checkout. Seeds, family/split,
lineage, instance/text hashes, witnesses, certificates and oracle counts remain
unchanged. Packaging changes code revision, as explained in `PILOT.md`; it does not
falsify earlier lineage. Sanitized evidence labels earlier 63-test results as the
original workspace validation, not the smaller package-specific test suite.

## Excluded

No corpus-v1 data (including its synthetic subset), IHTC/source-derived rows,
source ZIPs, adaptation generator, official validator, source-mapping scripts,
standalone workspace Git metadata, home-directory files, credentials, authentication
configuration, remote job scripts, private hostnames/paths, raw logs, cached files,
Library attachments or unrelated projects are included. Source redistribution
rights remain unverified and are not asserted here. The original source and v1
remain unchanged outside this checkout.

The original MIT notice applies to the original code and original synthetic files;
its exclusions for third-party data and evidence snapshots are retained. No extra
redistribution permission for third-party materials is implied.

The focused follow-up adds 40 tests (74 total), fixes revision validation and
incomplete usage reporting, and refreshes sanitized validation evidence. Fixture
bytes and original lineage remain unchanged; no new dataset cases or experiments
are added. The updated code revision is recorded in package-validation.json.
