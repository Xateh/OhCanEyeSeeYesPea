# Shared evaluation framework

**To:** Xu An, Allan, Benjamin (CS3263 Group 7)  
**From:** Benjamin (prompting / experiments / scoring)  
**Status:** team-agreed scoring freeze. Not a provider choice, spend approval, or authorization to run paid models.  
**Builds on:** merged `main` (PRs #1, #15–#18), especially `docs/benchmarking.md` and `tier_a_contract.py`.  
**Related issues:** [#7](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/7) freeze protocol; [#9](https://github.com/Xateh/OhCanEyeSeeYesPea/issues/9) aggregation (Xu An after this freeze).

---

## 1. What we are measuring

**Research question:** On identical surgery-scheduling text, does the same language model do better if it translates the problem for a CSP solver, compared with answering directly?

We are **not** asking whether a CSP can solve gold JSON (it should, if the instance is in range). That is only a baseline.

Three columns in the report:

| Approach | What it sees | Role |
|---|---|---|
| **LLM-only** (`no_tools`) | The case **text** | Direct prompting |
| **LLM+CSP** (`csp`) | The **same** text; model translates; solver runs on that translation | Main alternative |
| **CSP-on-gold** (optional) | The **gold structured instance**, no text | Ceiling if translation were perfect. Tokens = 0. Useful, not the main claim. |

The CSP never reads English. In LLM+CSP it only sees the model’s translated constraints. Scoring always uses **gold JSON** (the intended instance), never the translation.

---

## 2. What already exists (do not rebuild)

The repo already has the hard-constraint half of this framework:

- Paired harness: same text, `no_tools` vs `csp`, independent checker (`surgerybench/temporal_benchmark.py`).
- Mock translator only. Mock no-tools always returns `UNKNOWN`. That tests plumbing, **not** model quality.
- Frozen receipt scoring and paired summaries for Tier A (`tier_a_contract.py`).
- Checkers: `check_schedule`, `check_certificate`. Any checker-valid schedule can succeed; we do **not** require a byte-identical copy of the gold witness.

This note freezes **how we score** for the report. Prompts, token/time limits, repeats, and a real provider are still open (still #7 / #8).

---

## 3. Gold and legal answers

Every evaluation case needs:

- label `FEASIBLE` or `INFEASIBLE`
- a valid schedule (witness) or a valid infeasibility certificate

Allowed model/solver finals:

```json
{"status": "FEASIBLE", "schedule": [{"patient": "A", "day": 0, "start": 0, "room": "r0"}]}
{"status": "INFEASIBLE", "certificate": {"kind": "pair_order_impossible", "patients": ["A", "E"]}}
{"status": "UNKNOWN"}
```

**Hard constraints** (this is “correct”): arrival, deadline, eligible rooms, fixed surgeon, calendars, gaps, budgets, each mandatory surgery once, no overlap, no splitting.

`priority` and `emergency` are metadata only. Optional jobs may be omitted and still be hard-valid. **v1 has no soft-preference score.**

**UNKNOWN, timeout, and broken JSON are expected.** Real models omit fields, wrap JSON in prose, or hit API/solver limits. In this project a time/node limit must stay `UNKNOWN`, never `INFEASIBLE`. These rows stay in the denominator as **not-success**. Dropping them makes a method that guesses look better than one that abstains.

Gold is never used to repair a translation. Solving the **wrong** instance and then failing gold is a translation failure, not a solver win.

---

## 4. Quality metrics (headline)

Always report **numerator / denominator**. Do not drop failures to inflate accuracy.

| Metric | Denominator | Counts as success |
|---|---|---|
| **Evidence-backed success** | all planned cases for that approach | Valid schedule on gold-FEASIBLE **or** valid certificate on gold-INFEASIBLE |
| **Feasible-schedule success** | gold-FEASIBLE cases | `FEASIBLE` + schedule accepted on the **intended** instance |
| **Certified-infeasible success** | gold-INFEASIBLE cases | `INFEASIBLE` + certificate accepted on the intended instance |
| **Infeasible decision** (diagnostic only) | gold-INFEASIBLE cases | Status is `INFEASIBLE`, even if the proof is missing/invalid |
| **Status agreement** | all planned cases | Status equals the gold label (`UNKNOWN` is disagreement) |

**Report headline:** evidence-backed success.

**If we want one F1:** positive class = evidence-backed success vs everything else, **per approach**. Optional extra: **precision of FEASIBLE claims** = among outputs that said `FEASIBLE`, how often the schedule is valid on gold. Do **not** use naive label-F1 that treats an invalid schedule as a true positive.

Exact match to the gold witness is **not** a metric (many legal schedules exist).

---

## 5. Reliability and cost

Same cases, every approach.

**Reliability:** UNKNOWN rate, invalid-JSON / schema error rate, timeout rate, provider error rate, tool/solver error rate. Completion = well-formed final (or explicit abstention).

**Cost:**

- tokens in + out (and $ if we have a price)
- wall-clock per case
- LLM+CSP: solver time and number of CSP calls
- CSP-on-gold: runtime only (tokens = 0)

Accuracy without cost is incomplete for the report.

Do not average quality and cost into one number.

---

## 6. How we compare the two main approaches

For each case (and each repeat, if we later set R > 1):

- both succeeded
- LLM-only only
- LLM+CSP only
- neither
- incomplete (missing / not finished)

For LLM+CSP failures, split:

1. **Translation error** — including “CSP solved the translation, gold checker still fails”
2. **Solver UNKNOWN / timeout** on a translation that may be fine
3. **Bad output** — broken JSON / wrong shape

CSP-on-gold exists to tell (1) from (2): if gold solves and the translation does not (or solves a different problem), the LLM missed the constraints.

Summaries by approach, gold label, family / theme / split. Families are related; they are not IID samples. No p-value theatre on 24 families.

---

## 7. Data

**Now:** 48-case original-synthetic pilot (`fixtures/arrival-deadline-v1/`), family-disjoint train/val/test 32/8/8.

**Later:** expanded original-synthetic data is fine **if** every scored case still has a label plus witness/certificate. Same metrics.

**Do not mix** the 48-case files and the 15-case Tier A package as one table (`id` vs `case_id`; six Tier A `oracle_only` negatives are validation-only and must not enter model denominators).

Do not tune prompts or metrics on the test split.

---

## 8. Frozen decisions

1. Main comparison is **LLM-only vs LLM+CSP**. **CSP-on-gold** is an optional baseline, not a competing NLP method.
2. Headline numbers are **evidence-backed success**, **runtime**, and **tokens**.
3. UNKNOWN / timeout / bad JSON count as **not-success** and stay in the denominator.
4. **No soft-preference score** in v1 (optional coverage / priority / makespan are out until we define them in data).

---

## 9. What this does *not* freeze yet

Still needed after this agreement (issue #7 remainder):

- shared system / output instructions; arm-specific tool exposure; identical case text
- token, wall-clock, tool-call, retry limits; temperature / seed; number of repeats
- whether we include a second prompt style (basic vs structured)
- which corpus to use for the first real scored run (48-case pilot, Tier A’s 9 eligible cases, or the expanded set)

Then: Xu An implements aggregation against **these names** (#9). Allan’s OR-Tools adapter stays independent of scoring (#5). Real model + spend is a separate team decision (#8, #10).

---

## 10. Suggested report table

Three columns: LLM-only, LLM+CSP, CSP-on-gold.

Rows: evidence-backed success, feasible-schedule success, certified-infeasible success, UNKNOWN %, parse-error %, seconds/case, tokens/case.

That is enough to write the methods comparison without inventing extra metrics.

---

## Pointers

| File | Why |
|---|---|
| [`docs/data-and-semantics.md`](data-and-semantics.md) | Hard constraints; FEASIBLE / INFEASIBLE / UNKNOWN |
| [`docs/benchmarking.md`](benchmarking.md) | Provider envelope, leakage, existing score fields |
| [`surgerybench/temporal_benchmark.py`](../surgerybench/temporal_benchmark.py) | `score()`, paired `run()` |
| [`tier_a_contract.py`](../tier_a_contract.py) | Denominators, pair buckets, no silent repairs |
| [`docs/roadmap.md`](roadmap.md) | Ownership and remaining issues |
