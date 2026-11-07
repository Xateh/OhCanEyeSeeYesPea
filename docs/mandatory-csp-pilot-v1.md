# Mandatory-CSP protocol v1


Separate version requiring exactly one model-authored schema1.1 translation/tool call before CSP final; direct finals and extra calls fail, no repair. No-tools unchanged. Same case texts/model/settings/order as first pilot; no native tools or structured-output enforcement. Eight slots, at most12 HTTP turns and4 local CSP calls, no retries. Original intended-instance scoring and full denominators retained.

Conservative planning envelope:12 calls with12000 input and2000 output tokens each at pinned USD2/M input and10/M output =USD0.528, below USD1 intended ceiling; not a hard billing guarantee. Output2000/call, socket20s, attempt12000tokens/45s, oneCSP, zero retries, USD0.08 call allocation. Source pins and exact config recorded. Old source/evidence unchanged.

Implementation: responses_mandatory_runner.py; tests: tests/test_responses_mandatory.py. This is a separate treatment, not a replacement of optional-tool results. Real smoke results are archived under /home/t/tehxa/cs3263-review/mandatory-csp-pilot-20261107-_v7k_im2/RESULTS.md. Human/team study acceptance and publication are not implied.
