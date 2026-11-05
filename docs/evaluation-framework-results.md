# Claude scored under the shared evaluation framework

**Status:** preliminary, for team review. These numbers re-score runs recorded before the framework was agreed. No new model calls were made.
**Rulebook:** [`evaluation-framework.md`](evaluation-framework.md).
**Rerun:** `python3 -m study.framework_report` (needs matplotlib, makes no model calls).

## The short answer

- **Harder problems, Claude alone:** 98 of 100 were correct and backed by evidence.
- **48-case pilot, final test:** Claude alone and Claude with the solver both got 24 of 24, so the pilot can't show that either is better.
- **Cost on that test:** the solver route used about 2.9 times the tokens and 2 times the time.

The numbers match our earlier reports, because the old "fully correct" measure means the same as the framework's "evidence-backed success". The framework adds stricter reliability reporting, and it exposed one thing we must disclose: see "Runs that were replaced".

## What each measure means

| Measure | Plain meaning |
|---|---|
| Evidence-backed success | The answer was right **and** the independent checker accepted its schedule or proof. This is the headline. |
| Feasible-schedule success | On solvable problems, the schedule passed every rule. |
| Certified-infeasible success | On impossible problems, the proof passed the checker. |
| Infeasible decision | On impossible problems, Claude said "impossible", even without a good proof. Diagnostic only. |
| Status agreement | The yes/no answer matched, whether or not the evidence was good. |
| UNKNOWN | No answer was given, including when time ran out. |
| Parse errors | The reply couldn't be read. |

Every planned run stays in the denominator, so a failure can't quietly disappear.

## Pilot: the framework's main table

This is the held-out test split: 8 problems, each run 3 times with the frozen v3 prompt. CSP-on-gold gives the solver the correct problem directly, and it's deterministic, so it ran once per problem. The solver in the LLM+CSP and CSP-on-gold columns is the project's simple search.

| Measure | LLM-only | LLM+CSP | CSP-on-gold |
|---|--:|--:|--:|
| Evidence-backed success | 24/24 | 24/24 | 8/8 |
| Feasible-schedule success | 12/12 | 12/12 | 4/4 |
| Certified-infeasible success | 12/12 | 12/12 | 4/4 |
| Infeasible decision (diagnostic) | 12/12 | 12/12 | 4/4 |
| Status agreement | 24/24 | 24/24 | 8/8 |
| UNKNOWN | 0/24 | 0/24 | 0/8 |
| Parse errors | 0/24 | 0/24 | 0/8 |
| Timeouts | 0/24 | 0/24 | 0/8 |
| Provider errors | 0/24 | 0/24 | 0/8 |
| Tool or solver errors | 0/24 | 0/24 | 0/8 |
| Seconds per case (mean) | 4.9 | 9.7 | 0.0001 |
| Tokens per case (mean) | 2,130 | 6,159 | 0 |

![Time and tokens per case for each approach](../study/figures/framework-cost.png)

**What it means:** both approaches were perfect, so the only difference is cost. The solver itself took under a millisecond per case, so the extra time comes from Claude writing out the translation and then its final answer. Translating never went wrong: all 64 v3 translations across the splits matched the intended problem exactly, so the framework's failure split on the test split is 0 translation errors, 0 solver UNKNOWNs and 0 bad outputs.

### Comparison on the same runs

| Split | Runs per approach | LLM-only success | LLM+CSP success | Both | LLM-only only | LLM+CSP only | Neither | Incomplete |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| train | 32 | 32/32 | 32/32 | 32 | 0 | 0 | 0 | 0 |
| validation | 8 | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 0 |
| test | 24 | 24/24 | 24/24 | 24 | 0 | 0 | 0 | 0 |

The prompt was adjusted using the train split, so treat that row as development data. Every test theme scored 6/6 for both approaches. CSP-on-gold solved all 48 pilot problems.

Reliability did depend on the prompt. All of these are LLM+CSP on the train split:

| Prompt | LLM+CSP success | Solver actually called | Parse or format failures | Tool errors |
|---|--:|--:|--:|--:|
| v1 | 32/32 | 0/32 | 0/32 | 0/32 |
| v2 | 32/32 | 32/32 | 0/32 | 13/32 |
| v3 | 32/32 | 32/32 | 0/32 | 0/32 |

With v1, Claude skipped the optional solver every time, so those runs say nothing about the solver. With v2, 13 runs hit at least one tool error and recovered. Showing the format in v3 removed those errors.

## Harder dataset: first recorded planned attempts

Reporting revision 2 retains the first recorded 20-case attempt at every size, including operational failures. This is a correction of stored-receipt accounting under the frozen denominator rule, not a new model run or approval of the historical study protocol. Initial size40/size80 metadata records skipped=0 and each folder contains every expected case. Reruns are separate attempts, never replacement primary rows.

| Surgeries | Evidence-backed success | Feasible schedule | Certified negative | Provider failures | UNKNOWN |
|--:|--:|--:|--:|--:|--:|
| 5 | 20/20 | 10/10 | 10/10 | 0/20 | 0/20 |
| 10 | 20/20 | 10/10 | 10/10 | 0/20 | 0/20 |
| 20 | 20/20 | 10/10 | 10/10 | 0/20 | 0/20 |
| 40, initial | 4/20 | 2/10 | 2/10 | 16/20 | 16/20 |
| 80, initial | 0/20 | 0/10 | 0/10 | 20/20 | 20/20 |
| First attempts | 64/100 | 32/50 | 32/50 | 36/100 | 36/100 |

Operational failures are not wrong mathematical answers, but remain not-success in the planned denominator. These counts describe stored attempts, not100 independent samples or a general model-accuracy claim.

### Separate exploratory reruns

| Repeated cases | Evidence-backed success | Feasible schedule | Certified negative | Timeout |
|--:|--:|--:|--:|--:|
| 40 surgeries | 19/20 | 9/10 | 10/10 | 0/20 |
| 80 surgeries | 19/20 | 9/10 | 10/10 | 1/20 |
| Reruns only | 38/40 | 18/20 | 20/20 | 1/40 |

These40 attempts repeat original cases. The former98/100 table combined60 first-attempt outcomes with40 reruns; its original generated JSON/charts are preserved as historical exploratory artifacts, not the primary failure-retaining cohort. No retry policy is retrospectively approved here.

Saved-cost coverage is64/100 first attempts (known subtotal USD4.060184), and39/40 reruns (known subtotal USD10.764208). Complete costs remain unknown. No missing charge is replaced with zero. See [correction scope and limitations](pr21-reporting-corrections.md).

## Limits to keep in mind

- **Not the official run:** the framework says it doesn't approve paid runs, and it leaves prompts, limits, repeats and the corpus for the first scored run still open (issue #7). The v3 prompt and the 5-minute limit were this study's own choices.
- **No winner yet:** on the pilot both approaches hit the ceiling. On the harder set only Claude alone ran. The framework's question, whether a solver helps, stays open until LLM+CSP runs there with the team's solver.
- **Few independent cases:** the 24 test runs come from 8 problems, and problems in a family are related. So this report gives counts only, without p-values, as the framework asks. The p-value in the first study report shouldn't go in the final report.
- **F1 is our reading:** the framework names the positive class but not the exact formula. We treated any FEASIBLE or INFEASIBLE reply as a positive claim and every planned run as a positive case. The team should confirm that.
- **Historical usage is incomplete:** provider failures and one rerun timeout lack saved complete usage. Report known subtotals and coverage, not a fabricated complete bill.
- **Close to best-case conditions:** regular wording, one kind of impossibility, feasibility only and one attempt per harder problem, as described in [`hard-dataset-study.md`](hard-dataset-study.md).

## Attempt provenance retained

The canonical loader pins first-attempt folders in HARD_PRIMARY and later folders in HARD_RERUNS, validates exact case membership and keeps them separate. Original raw receipts and prior report artifacts remain unchanged. The team still needs a prospective retry/stopping protocol; retaining initial failures is the conservative frozen-rule default, not retrospective permission for these historical runs.
