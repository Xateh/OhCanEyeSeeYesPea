# Local benchmark P2 corrections

Based on merged main 0d146e1321695a022cb9793188bb00b9c7adc75f. PR24 and its separate strict-v2 follow-up remain untouched. No live API requests, credentials or historical sensitive outputs are needed for these regressions.

## Planned costs

`cost_summary` accepts an explicit planned-run denominator. Paired runner v4 and the copied Responses runner summaries pass it for each arm. Missing planned slots make the complete cost unknown while retaining observed known subtotals and coverage. Execution/scheduling calls that summarize received receipts alone retain their existing semantics: an unstarted next attempt is not fabricated as an observed charge. No billing statement or zero charge is inferred for a missing planned attempt.

## Bounded dataset reads

Audit revision seeded-v2-audit-bounded-io-v3 preflights every entry's regular-file type, no-symlink status and 2 MiB limit before reading any payload. Directory and child descriptors are pinned with no-follow flags; post-open fstat rechecks type/size, and bounded reads reject growth. Entry count is bounded. The exact original auditor hash and exact preceding portability-v2 hash remain explicitly recognized, with all other source hashes and existing semantic/label/evidence checks intact. This is a narrow documented compatibility whitelist, not arbitrary source acceptance. Stored manifests, fixtures, labels and old results are never rewritten.

## Legacy HTTP retention

Five legacy raw-HTTP transports now share `responses_http_v2` and advertise transport revision v2. Model identities, API bodies, prompts, output schemas, native-tool policy, account route and no-retry policy are unchanged. New bindings pin the helper source. Returned chunks accumulate only to the existing envelope limit plus one byte. Incomplete reads, timeouts and non-timeout read failures retain bounded data/status/safe headers; adapters preserve timeout classification, reject incomplete data and keep observed usage/cost unknown. A complete-looking partial JSON object is not parsed as a completed response.

Full credential echoes and an incomplete body's trailing prefix of the credential are redacted before retention, including echoes split across chunks. This does not claim to detect arbitrary transformed or independently echoed secret fragments. Bytes never returned by a failing read cannot be reconstructed; local timeout does not guarantee remote cancellation. There is no retry or output repair. The official SDK already had corresponding bounded-chunk/timeout/prefix-redaction handling; it is regression-tested without replacing its transport. Its only local change here is planned-slot cost reporting.

## Source identity and historical replay

Historical artifacts and their declared hashes remain byte-for-byte unchanged. Changed runner/transport/accounting sources deliberately change new source bindings; old saved plans must be replayed with their exact previously pinned source checkout, not relabeled or silently rebound. No historical requests, estimates or assessments are edited. SDK/calibration case selection and resource caps remain unchanged. These are local fixes pending review and separate publication authority.

## Verification

Synthetic-only regressions run through Slurm, normal partition, requesting one CPU per task and 1 GiB (Slurm accounted two allocated logical CPUs for each job), with each command capped at 60 seconds and the existing network-blocking/one-worker harness. Cases cover entirely missing and partially received planned costs, pre-read rejection of oversized/symlink/non-file entries, truncated synthetic-key echoes, chunk retention, timeout/error classification, UTF-8 failures and offline raw-record reassessment. The wider normal/optimized suite and pinned optional SDK checks are recorded separately from historical CI receipts.

EOF review correction: the bounded legacy reader now checks remaining declared
Content-Length when read1 returns empty, and checks chunked termination. A short
framed body remains incomplete even if its retained prefix is valid JSON; it is
not parsed/scored and its usage stays unknown. Synthetic real HTTPResponse tests
cover premature EOF, complete/missing chunk terminators and boundary redaction.
Descriptor tests observe os.read directly and cover replacement before/after open
and growth before/after fstat. An already opened regular inode stays pinned after
path replacement. EOF-delimited responses without declared framing cannot expose
an undeclared intended length; no remote cancellation is promised.
