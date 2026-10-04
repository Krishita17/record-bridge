"""Evaluation: measure detection accuracy against the dirtifier's ground truth.

Because the dirtifier labels every injected error and duplicate, we can report
precision/recall for both validation and duplicate matching -- turning a demo
into an evaluated tool.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass
class PRF:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d.update(precision=round(self.precision, 4), recall=round(self.recall, 4), f1=round(self.f1, 4))
        return d


def evaluate_validation(errors: pd.DataFrame, gt_errors: pd.DataFrame) -> dict:
    """Row-level: did we flag the rows the dirtifier corrupted (error severity)?"""
    flagged = set(errors.loc[errors["severity"] == "error", "row_index"].astype(int))
    truth = set(gt_errors["row_index"].astype(int))
    tp = len(flagged & truth)
    fp = len(flagged - truth)
    fn = len(truth - flagged)
    overall = PRF(tp, fp, fn)

    per_type = {}
    for etype, grp in gt_errors.groupby("error_type"):
        t = set(grp["row_index"].astype(int))
        caught = len(t & flagged)
        per_type[etype] = {"injected": len(t), "caught": caught,
                           "recall": round(caught / len(t), 4) if len(t) else 0.0}
    return {"overall": overall.as_dict(), "per_type": per_type}


def evaluate_dedupe(pairs: pd.DataFrame, gt_dupes: pd.DataFrame) -> dict:
    """Pair-level: did we match each duplicate to its source row?

    A detected pair counts as a true positive if it links a dirtifier duplicate
    (row_index) to its source (of_row_index), in either order.
    """
    truth_pairs = {
        frozenset((int(r.row_index), int(r.of_row_index)))
        for r in gt_dupes.itertuples()
    }
    detected = {
        frozenset((int(r.record_a), int(r.record_b)))
        for r in pairs.itertuples()
    }
    tp = len(truth_pairs & detected)
    fp = len(detected - truth_pairs)
    fn = len(truth_pairs - detected)
    prf = PRF(tp, fp, fn)

    by_type = {}
    for dtype, grp in gt_dupes.groupby("dup_type"):
        t = {frozenset((int(r.row_index), int(r.of_row_index))) for r in grp.itertuples()}
        caught = len(t & detected)
        by_type[dtype] = {"injected": len(t), "caught": caught,
                          "recall": round(caught / len(t), 4) if len(t) else 0.0}
    return {"overall": prf.as_dict(), "by_type": by_type}
