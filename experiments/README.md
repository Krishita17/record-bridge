# Experiments

Every result in this repo is reproducible from a seed.

| Setting      | Default | Flag                     |
|--------------|---------|--------------------------|
| records      | 5000    | `--n`                    |
| error rate   | 0.15    | `--error-rate`           |
| seed         | 42      | `--seed`                 |
| batches      | 5       | `--batches` (for `all`)  |

Reproduce the headline run:

```bash
recordbridge all --n 5000 --error-rate 0.15 --seed 42 --batches 5
```

The `all` command runs several successive batches (seeds `42..46`) to populate the
quality-over-batches trend, evaluates the final batch against its ground truth,
and writes:

- `results/metrics.json` — precision/recall for validation and deduplication.
- `figures/*.png` — every README figure.
- `reports/*.md` — exception report and audit excerpt.
- `dashboard/recordbridge_dashboard.html` — the interactive dashboard.

## Tuning the duplicate thresholds

The precision/recall trade-off of the fuzzy resolver is controlled in
`config/rules.yaml`:

```yaml
fuzzy:
  auto_merge_threshold: 92   # >= -> auto-merge
  review_threshold: 80       # [80, 92) -> hold for review
```

Raise `auto_merge_threshold` for higher merge precision (fewer wrong merges, more
holds); lower it for higher recall. Borderline pairs are always held, never
silently merged.
