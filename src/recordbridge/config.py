"""Configuration loader for RecordBridge.

Validation rules and duplicate-matching parameters live in an external YAML
file (``config/rules.yaml`` by default) so the pipeline generalises to any
records domain without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = Path("config/rules.yaml")


@dataclass
class FuzzyConfig:
    name_fields: list[str] = field(default_factory=lambda: ["first_name", "last_name"])
    dob_field: str = "dob"
    auto_merge_threshold: float = 92.0
    review_threshold: float = 80.0
    blocking: str = "last_initial"


@dataclass
class Config:
    dataset: str
    schema: list[str]
    exact_keys: list[str]
    fuzzy: FuzzyConfig
    rules: list[dict[str, Any]]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_RULES_PATH) -> "Config":
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        fuzzy_raw = data.get("fuzzy", {}) or {}
        fuzzy = FuzzyConfig(
            name_fields=fuzzy_raw.get("name_fields", ["first_name", "last_name"]),
            dob_field=fuzzy_raw.get("dob_field", "dob"),
            auto_merge_threshold=float(fuzzy_raw.get("auto_merge_threshold", 92)),
            review_threshold=float(fuzzy_raw.get("review_threshold", 80)),
            blocking=fuzzy_raw.get("blocking", "last_initial"),
        )
        return cls(
            dataset=data.get("dataset", "dataset"),
            schema=data.get("schema", []),
            exact_keys=data.get("exact_keys", []),
            fuzzy=fuzzy,
            rules=data.get("rules", []),
            raw=data,
        )
