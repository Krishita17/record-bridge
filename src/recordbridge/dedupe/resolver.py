"""Duplicate resolver -- the technical heart of RecordBridge.

Two stages:
  1. Exact match on strong keys (student_id, email).
  2. Fuzzy match on name + DOB similarity (RapidFuzz), within blocks.

Each candidate pair gets a similarity score and a routed resolution:
  * auto-merge  (score >= auto_merge_threshold)  -- high confidence
  * hold        (review_threshold <= score < auto_merge)  -- manual review
  * keep        (score < review_threshold)  -- clearly distinct

Borderline pairs are NEVER silently merged: they are routed to 'hold'. A wrong
merge in a real records system is a serious error.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from rapidfuzz import fuzz

from ..config import FuzzyConfig


@dataclass
class DedupeResult:
    pairs: list[dict] = field(default_factory=list)  # one per detected pair
    # row_index -> resolution route applied ('auto-merge' loser, 'hold', 'keep')
    row_disposition: dict[int, str] = field(default_factory=dict)

    def pairs_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.pairs,
            columns=["record_a", "record_b", "match_type", "similarity_score", "resolution"],
        )

    @property
    def n_auto_merge(self) -> int:
        return sum(1 for p in self.pairs if p["resolution"] == "auto-merge")

    @property
    def n_hold(self) -> int:
        return sum(1 for p in self.pairs if p["resolution"] == "hold")

    @property
    def n_keep(self) -> int:
        return sum(1 for p in self.pairs if p["resolution"] == "keep")


class DuplicateResolver:
    def __init__(self, fuzzy: FuzzyConfig, exact_keys: list[str]):
        self.fuzzy = fuzzy
        self.exact_keys = exact_keys

    # -- helpers -------------------------------------------------------------
    def _name_blob(self, row) -> str:
        parts = [str(row.get(f, "")).strip().lower() for f in self.fuzzy.name_fields]
        return " ".join(p for p in parts if p)

    def _block_key(self, row) -> str:
        if self.fuzzy.blocking == "last_initial":
            last = str(row.get("last_name", "")).strip().lower()
            return last[:1] if last else "_"
        return "_"  # single block: compare all (small datasets)

    def _score(self, row_a, row_b) -> float:
        name_a, name_b = self._name_blob(row_a), self._name_blob(row_b)
        name_score = fuzz.token_sort_ratio(name_a, name_b)
        dob_a = str(row_a.get(self.fuzzy.dob_field, "")).strip()
        dob_b = str(row_b.get(self.fuzzy.dob_field, "")).strip()
        # DOB is a strong discriminator: exact match boosts, mismatch penalises.
        if dob_a and dob_b and dob_a == dob_b:
            return min(100.0, 0.7 * name_score + 30.0)
        if dob_a and dob_b and dob_a != dob_b:
            return 0.6 * name_score
        return 0.7 * name_score  # one DOB missing: rely mostly on name

    def _route(self, score: float) -> str:
        if score >= self.fuzzy.auto_merge_threshold:
            return "auto-merge"
        if score >= self.fuzzy.review_threshold:
            return "hold"
        return "keep"

    # -- driver --------------------------------------------------------------
    def resolve(self, df: pd.DataFrame, *, index_col: str = "row_index") -> DedupeResult:
        result = DedupeResult()
        records = df.to_dict("records")
        seen_exact: dict[tuple, int] = {}

        # Stage 1: exact match on strong keys.
        matched_exact: set[int] = set()
        for rec in records:
            ref = rec[index_col]
            for key in self.exact_keys:
                val = str(rec.get(key, "")).strip().lower()
                if not val:
                    continue
                k = (key, val)
                if k in seen_exact:
                    a = seen_exact[k]
                    result.pairs.append(
                        {
                            "record_a": a,
                            "record_b": ref,
                            "match_type": "exact",
                            "similarity_score": 100.0,
                            "resolution": "auto-merge",
                        }
                    )
                    result.row_disposition[ref] = "auto-merge"
                    matched_exact.add(ref)
                    break
                seen_exact[k] = ref

        # Stage 2: fuzzy match within blocks (skip rows already exact-merged).
        blocks: dict[str, list[dict]] = {}
        for rec in records:
            if rec[index_col] in matched_exact:
                continue
            blocks.setdefault(self._block_key(rec), []).append(rec)

        for block in blocks.values():
            for i in range(len(block)):
                for j in range(i + 1, len(block)):
                    ra, rb = block[i], block[j]
                    ref_a, ref_b = ra[index_col], rb[index_col]
                    score = self._score(ra, rb)
                    route = self._route(score)
                    if route == "keep":
                        continue  # distinct: don't record noise
                    result.pairs.append(
                        {
                            "record_a": ref_a,
                            "record_b": ref_b,
                            "match_type": "fuzzy",
                            "similarity_score": round(score, 2),
                            "resolution": route,
                        }
                    )
                    # The higher row_index is the 'loser' (duplicate submission).
                    loser = max(ref_a, ref_b)
                    # Never downgrade an auto-merge disposition to hold.
                    if result.row_disposition.get(loser) != "auto-merge":
                        result.row_disposition[loser] = route
        return result
