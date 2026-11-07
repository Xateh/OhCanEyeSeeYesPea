# Frozen final-step schema diagnostic v1

Only generation-format enforcement changes. ON retains saved Responses text.format; OFF omits text. Instructions, original task text, saved model-authored solver input/result, model, effort, tier and all other fields are identical within each case. No translation or solver is rerun. Order: fragmented OFF/ON, eligibility ON/OFF. One repetition, four calls, zero solver calls. Exact source receipts and payload/source/schema hashes are pinned in plan-frozen.json.

Both conditions retain strict unmodified JSON parsing, identical required final-envelope shape and intended-instance checking. OFF does not accept fences, repair, wrong shapes, wrong schedules or UNKNOWN as success. gpt-6-astra/high, Standard default, 2000 output tokens including reasoning, 20-second socket/call setting, 45-second/12000-token attempt allocation, 7500 request bytes, no retries/fallback and USD0.80 intended spend apply. Exact-body reserve USD0.722825; maximum-byte reserve USD0.7878. These are not guaranteed billing or remote-cancellation caps.

Prior sources/results remain unchanged. Code/tests/docs are AI-assisted, not human/team sign-off or publication approval.
