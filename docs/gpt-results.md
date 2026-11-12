# GPT-6 Astra vs Claude Opus 5.5 on surgery scheduling

**Status:** preliminary, for team review. Scored with [`evaluation-framework.md`](evaluation-framework.md); every planned run stays in the denominator.
**GPT:** `gpt-6-astra`, high effort, through the official OpenAI Python SDK (`study/openai_provider.py`, run 12 November 2026).
**Claude:** `claude-opus-5-5`, high effort, through the Claude Code CLI (the recorded runs).
**Same for both:** the frozen v3 prompt word for word, the same problems and repetitions, the same OR-Tools solver and the same independent checker.
**Rerun the scoring:** `.venv/bin/python -m study.api_report --provider openai` (makes no model calls).

## The short answer

- **48-problem set:** GPT and Claude were both perfect, alone and with OR-Tools: 64/64 each across train, validation and test.
- **Harder problems up to 40 surgeries (80 problems):**
  - **With OR-Tools:** both models were right 80/80.
  - **Alone:** Claude 79/80, GPT 75/80. All 5 GPT misses were unreadable replies on impossible problems, not wrong schedules.
- **GPT used about half the tokens but cost about the same,** because its tokens cost 2.5× as much. Speed was similar.
- **The 80-surgery problems were not finished within the $30 budget.** GPT alone got 3 of the first 4 right; the 4th timed out.

## 48-problem set (train 32, validation 8, test 8 × 3 runs)

| Measure | Claude alone | GPT alone | Claude + OR-Tools | GPT + OR-Tools |
|---|--:|--:|--:|--:|
| Evidence-backed success | 64/64 | 64/64 | 64/64 | 64/64 |
| Errors of any kind | 0 | 0 | 0 | 0 |
| Seconds per problem | 4.5 | 4.1 | 9.5 | 11.7 |
| Tokens per problem | 2,035 | 834 | 5,995 | 3,218 |
| Estimated cost (USD) | 0.74 | 0.81 | 3.00 | 3.23 |

## Harder problems, 5 to 40 surgeries (20 problems each, half impossible)

| Surgeries | Claude alone | GPT alone | Claude + OR-Tools | GPT + OR-Tools |
|--:|--:|--:|--:|--:|
| 5 | 20/20 | 20/20 | 20/20 | 20/20 |
| 10 | 20/20 | 18/20 | 20/20 | 20/20 |
| 20 | 20/20 | 19/20 | 20/20 | 20/20 |
| 40 | 19/20 | 18/20 | 20/20 | 20/20 |
| **Total** | **79/80** | **75/80** | **80/80** | **80/80** |

| Measure (all 80) | Claude alone | GPT alone | Claude + OR-Tools | GPT + OR-Tools |
|---|--:|--:|--:|--:|
| Feasible-schedule success | 39/40 | 40/40 | 40/40 | 40/40 |
| Certified-infeasible success | 40/40 | 35/40 | 40/40 | 40/40 |
| Unreadable replies (parse errors) | 0 | 5 | 0 | 0 |
| Seconds per problem | 28 | 30 | 19 | 22 |
| Tokens per problem | 6,371 | 3,172 | 12,844 | 7,888 |
| Estimated cost (USD) | 6.87 | 7.24 | 10.44 | 12.58 |

Claude alone uses the complete view with reruns. Its official first attempt lost runs to the account usage limit (see `framework-summary.json`).

**What the numbers mean:**
- **Different mistakes:**
  - Claude alone's one miss was a real scheduling error: a double-booked surgeon at 40 surgeries.
  - GPT alone never produced a wrong schedule. Its 5 misses were replies the checker could not read as JSON, all on impossible problems and all breaking at the same character (122). That points to one repeated formatting slip near the end of the impossibility proof. The broken text is not stored (nor in the Claude runs), so the exact slip cannot be shown.
- **The solver evens the models out:** with OR-Tools both were perfect. GPT + OR-Tools fixed all 5 of GPT's misses and broke none. Claude + OR-Tools fixed Claude's one miss.
- **Agreement:** Claude alone and GPT alone were both right on 74 problems; Claude alone only on 5, GPT alone only on 1.
- **Cost:** GPT needs fewer tokens, but at $10 / $50 per million against Claude's $4 / $20 it costs about the same to slightly more.

## 80 surgeries: not finished

- **GPT alone:** 4 of 20 problems ran. 3 were right; 1 feasible problem timed out after 300 s (the SDK retried it twice, 902 s in total).
- **Why it stopped:** a timed-out call reports no usage, so its cost is unknown. The runner stops on unknown cost, as the framework's cost rules require.
- **Budget:** finishing the remaining 36 runs (16 alone, 20 with OR-Tools) would cost about $15 more, past the $30 limit. The runner resumes where it stopped: `python -m study.run_api --provider openai --arm alone --cohort hard-n80 --budget 15`, then `--arm ortools`.
- **Reporting:** because 80 surgeries is incomplete, `api_report` refuses to give a harder-set total, and these tables stop at 40 surgeries. Do not compare against Claude's 100-problem totals.

## Spend

About **US$24.82** of estimated usage, plus the unknown cost of the one timed-out call. These are estimates at standard rates (GPT-6 Astra $10 / $50 per million tokens, from secondary pricing sites that match Xu An's recorded smoke test exactly), not the bill.

## Limits

- **Different access routes:** GPT ran through the SDK, Claude through the CLI.
- **One run per harder problem,** one prompt, tidy problems, feasibility only.
- **SDK retries:** the OpenAI SDK retries timeouts by default (2 retries), so a GPT call could wait up to 3 × 300 s; Claude CLI calls stopped at 300 s. This only touched the one timed-out problem, which still failed.
- **Prompt tuning:** the v3 prompt was tuned on Claude. GPT's formatting slips might disappear with a prompt tuned for it.
