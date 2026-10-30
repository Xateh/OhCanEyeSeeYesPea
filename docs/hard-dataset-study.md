# Claude alone on harder surgery problems (unfinished)

**Status:** sizes 5, 10 and 20 are complete. Sizes 40 and 80 were cut off by a Claude Pro 5-hour usage limit, so this study is not finished.

Model: `claude-opus-5-5` at `high` effort, with no tools and no solver. Dataset: `fixtures/hard-synthetic-v1`, 100 problems in 50 matched pairs. Surgery lengths come from [German hospital data](https://doi.org/10.5281/zenodo.7147921) (CC BY 4.0).

| Surgeries | Problems finished | Fully correct | Valid schedules | Valid proofs | Median time (s) | Median output tokens |
|--:|--:|---|---|---|--:|--:|
| 5 | 20 | 20/20 | 10/10 | 10/10 | 8.1 | 732 |
| 10 | 20 | 20/20 | 10/10 | 10/10 | 15.1 | 1,441 |
| 20 | 20 | 20/20 | 10/10 | 10/10 | 30.1 | 3,315 |
| 40 | 4 of 20 | 4/4 | 2/2 | 2/2 | 46.4 | 5,317 |
| 80 | 0 of 20 | not run | not run | not run | n/a | n/a |

**Do not report size 40 as a result:** 4 problems is too few, and they were simply the first to finish. The 16 usage-limit failures are not Claude mistakes and are excluded from the scores.

## To finish

After the limit resets, run these, then build the charts:

    mv study/results/hard-n40-partial-usage-limit /tmp/
    python3 -m study.run_hard --size 40 --budget 5
    python3 -m study.run_hard --size 80 --budget 5
