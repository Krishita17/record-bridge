"""Synthetic student data generator and dirtifier.

RecordBridge NEVER uses real student data. ``generate_clean`` produces a clean
Faker-based base; ``dirtify`` injects realistic, *labelled* errors so detection
accuracy can be measured against ground truth. Everything is seeded and fully
reproducible.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

PROGRAMS = [
    "Computer Science",
    "Mechanical Engineering",
    "Biology",
    "Business Administration",
    "Psychology",
    "Economics",
    "Nursing",
    "Political Science",
    "Mathematics",
    "English Literature",
]

COLUMNS = [
    "student_id",
    "first_name",
    "last_name",
    "dob",
    "email",
    "phone",
    "program",
    "gpa",
]


@dataclass
class GroundTruth:
    """Records exactly which rows the dirtifier corrupted, and how.

    ``errors`` is a list of dicts: {row_index, field, error_type}.
    ``duplicates`` is a list of dicts: {row_index, of_row_index, dup_type}
        (dup_type is 'exact' or 'near'), i.e. row_index is a duplicate of
        of_row_index.
    """

    errors: list[dict] = field(default_factory=list)
    duplicates: list[dict] = field(default_factory=list)

    def errors_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.errors, columns=["row_index", "field", "error_type"])

    def duplicates_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.duplicates, columns=["row_index", "of_row_index", "dup_type"]
        )


def generate_clean(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate ``n`` clean, valid synthetic student records."""
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    rows = []
    for i in range(n):
        first = fake.first_name()
        last = fake.last_name()
        dob = fake.date_of_birth(minimum_age=17, maximum_age=30)
        # Unique, deterministic email to keep clean data genuinely clean.
        email = f"{first.lower()}.{last.lower()}{i}@example.edu"
        rows.append(
            {
                "student_id": f"S{i + 1:07d}",
                "first_name": first,
                "last_name": last,
                "dob": dob.isoformat(),
                "email": email,
                "phone": fake.numerify("###-###-####"),
                "program": rng.choice(PROGRAMS),
                "gpa": round(rng.uniform(2.0, 4.0), 2),
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def _typo(text: str, rng: random.Random) -> str:
    """Introduce a single realistic typo into a string."""
    if len(text) < 2:
        return text + text
    i = rng.randrange(len(text))
    op = rng.choice(["swap", "drop", "dup", "sub"])
    chars = list(text)
    if op == "swap" and i < len(chars) - 1:
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    elif op == "drop":
        del chars[i]
    elif op == "dup":
        chars.insert(i, chars[i])
    else:  # sub
        chars[i] = rng.choice("abcdefghijklmnopqrstuvwxyz")
    return "".join(chars)


def dirtify(
    clean: pd.DataFrame,
    error_rate: float = 0.15,
    seed: int = 42,
) -> tuple[pd.DataFrame, GroundTruth]:
    """Inject ~``error_rate`` labelled errors and duplicates into clean data.

    Returns the dirty DataFrame (with a stable ``row_index`` column) and a
    :class:`GroundTruth` describing every injected problem.
    """
    rng = random.Random(seed)
    df = clean.copy().reset_index(drop=True)
    df.insert(0, "row_index", range(len(df)))
    gt = GroundTruth()

    n = len(df)
    n_corrupt = int(n * error_rate)
    # Reserve a share of the corruption budget for duplicates.
    n_dupes = max(1, n_corrupt // 3)
    n_field_errors = n_corrupt - n_dupes

    field_error_kinds = [
        ("missing_required", ["first_name", "last_name", "dob", "email", "student_id"]),
        ("bad_email", ["email"]),
        ("bad_date", ["dob"]),
        ("out_of_range_gpa", ["gpa"]),
        ("future_dob", ["dob"]),
        ("name_typo", ["first_name", "last_name"]),
        ("bad_student_id", ["student_id"]),
    ]

    # --- field-level errors -------------------------------------------------
    target_rows = rng.sample(range(n), min(n_field_errors, n))
    for row_idx in target_rows:
        kind, fields = rng.choice(field_error_kinds)
        fld = rng.choice(fields)
        val = df.at[row_idx, fld]

        if kind == "missing_required":
            df.at[row_idx, fld] = ""
        elif kind == "bad_email":
            df.at[row_idx, "email"] = str(val).replace("@", "_at_")
            fld = "email"
        elif kind == "bad_date":
            # e.g. 03/14/2001 or 14-03-2001 -> non-ISO, ambiguous
            df.at[row_idx, "dob"] = rng.choice(["03/14/2001", "14-03-01", "not a date"])
            fld = "dob"
        elif kind == "out_of_range_gpa":
            df.at[row_idx, "gpa"] = rng.choice([4.7, 5.2, -1.0, 9.9])
            fld = "gpa"
        elif kind == "future_dob":
            future = date.today() + timedelta(days=rng.randint(30, 3650))
            df.at[row_idx, "dob"] = future.isoformat()
            fld = "dob"
        elif kind == "name_typo":
            df.at[row_idx, fld] = _typo(str(val), rng)
        elif kind == "bad_student_id":
            df.at[row_idx, "student_id"] = rng.choice(["XYZ", "123", "S12"])
            fld = "student_id"

        gt.errors.append({"row_index": row_idx, "field": fld, "error_type": kind})

    # --- duplicates ---------------------------------------------------------
    new_rows = []
    next_index = n
    source_pool = [i for i in range(n) if i not in set(target_rows)] or list(range(n))
    for _ in range(n_dupes):
        src = rng.choice(source_pool)
        dup = df.loc[df["row_index"] == src].iloc[0].to_dict()
        dup = dict(dup)
        dup["row_index"] = next_index

        if rng.random() < 0.5:
            dup_type = "exact"  # same person, duplicate submission
        else:
            dup_type = "near"
            # Near-duplicate: typo the name, keep DOB, vary id/email slightly.
            dup["first_name"] = _typo(str(dup["first_name"]), rng)
            dup["student_id"] = f"S{next_index + 1:07d}"
            dup["email"] = str(dup["email"]).replace("@", f".dup{next_index}@")

        new_rows.append(dup)
        gt.duplicates.append(
            {"row_index": next_index, "of_row_index": src, "dup_type": dup_type}
        )
        next_index += 1

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Shuffle so duplicates are not adjacent (realistic multi-source intake),
    # but keep the stable row_index as the ground-truth join key.
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df, gt


def write_dataset(
    out_dir: str | Path = "data",
    n: int = 5000,
    error_rate: float = 0.15,
    seed: int = 42,
) -> dict[str, Path]:
    """Generate clean + dirty datasets and ground truth; write them to disk."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clean = generate_clean(n=n, seed=seed)
    dirty, gt = dirtify(clean, error_rate=error_rate, seed=seed)

    paths = {
        "clean": out_dir / "students_clean_source.csv",
        "dirty": out_dir / "students_raw_intake.csv",
        "gt_errors": out_dir / "ground_truth_errors.csv",
        "gt_dupes": out_dir / "ground_truth_duplicates.csv",
    }
    clean.to_csv(paths["clean"], index=False)
    dirty.to_csv(paths["dirty"], index=False)
    gt.errors_df().to_csv(paths["gt_errors"], index=False)
    gt.duplicates_df().to_csv(paths["gt_dupes"], index=False)
    return paths
