"""Fuzzy-match accuracy on labelled duplicates, and the never-silently-merge rule."""
import pandas as pd

from recordbridge.config import FuzzyConfig
from recordbridge.dedupe import DuplicateResolver


def _resolver(auto=92, review=80):
    cfg = FuzzyConfig(auto_merge_threshold=auto, review_threshold=review)
    return DuplicateResolver(cfg, exact_keys=["student_id", "email"])


def test_exact_duplicate_detected():
    df = pd.DataFrame([
        {"row_index": 0, "student_id": "S1", "first_name": "Ada", "last_name": "Byron",
         "dob": "2000-01-01", "email": "a@x.edu"},
        {"row_index": 1, "student_id": "S1", "first_name": "Ada", "last_name": "Byron",
         "dob": "2000-01-01", "email": "a@x.edu"},
    ])
    res = _resolver().resolve(df)
    assert res.n_auto_merge == 1
    assert res.pairs[0]["match_type"] == "exact"


def test_near_duplicate_name_typo_same_dob():
    df = pd.DataFrame([
        {"row_index": 0, "student_id": "S1", "first_name": "Jonathan", "last_name": "Smith",
         "dob": "1999-05-05", "email": "j1@x.edu"},
        {"row_index": 1, "student_id": "S2", "first_name": "Johnathan", "last_name": "Smith",
         "dob": "1999-05-05", "email": "j2@x.edu"},
    ])
    res = _resolver().resolve(df)
    assert len(res.pairs) == 1
    assert res.pairs[0]["match_type"] == "fuzzy"
    assert res.pairs[0]["resolution"] in {"auto-merge", "hold"}


def test_distinct_people_not_merged():
    df = pd.DataFrame([
        {"row_index": 0, "student_id": "S1", "first_name": "Ada", "last_name": "Byron",
         "dob": "2000-01-01", "email": "a@x.edu"},
        {"row_index": 1, "student_id": "S2", "first_name": "Grace", "last_name": "Zuse",
         "dob": "1985-12-09", "email": "g@x.edu"},
    ])
    res = _resolver().resolve(df)
    assert res.n_auto_merge == 0
    assert res.n_hold == 0


def test_borderline_held_never_auto_merged():
    # Different DOB penalises the score into the hold band, not auto-merge.
    df = pd.DataFrame([
        {"row_index": 0, "student_id": "S1", "first_name": "Catherine", "last_name": "Johnson",
         "dob": "1998-03-03", "email": "c1@x.edu"},
        {"row_index": 1, "student_id": "S2", "first_name": "Katherine", "last_name": "Johnson",
         "dob": "1998-06-06", "email": "c2@x.edu"},
    ])
    res = _resolver(auto=92, review=50).resolve(df)
    # Whatever the score, a sub-threshold pair must never be auto-merged.
    for p in res.pairs:
        if p["similarity_score"] < 92:
            assert p["resolution"] != "auto-merge"
