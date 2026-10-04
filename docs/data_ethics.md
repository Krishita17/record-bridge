# Data Ethics & Scope

RecordBridge is a **data-integrity and governance pipeline** for student records,
demonstrated on **synthetic data**. The deliverable is a clean dataset plus an
auditable change history — the same artifacts a real records office produces for
compliance.

## Synthetic-only, no PII

- The repository ships a **Faker-based generator** and a **dirtifier**; it
  contains **no real student data**.
- Any external realism (e.g. shaping GPA or program distributions) must come from
  **aggregate statistics only** (such as public IPEDS tables) — **never real
  individuals**.
- This is the privacy guarantee that lets RecordBridge be open source: you can
  clone and run the entire pipeline from a seed with zero privacy risk.

## Governance framing (FERPA-style thinking)

The audit log and correction model mirror sound data-stewardship principles:

- **Traceability** — every value in `students_clean` can be traced back through
  `correction_log` to its untouched `students_staging` row.
- **Least surprise / no silent edits** — every normalisation, merge, and hold is
  recorded with field, old→new, action, who, and when.
- **Nothing silently dropped** — rows that fail validation are preserved as
  exceptions for staff to act on, not discarded.

This project **models** governance thinking; it is not a compliance product. In a
real deployment, access control, encryption, retention policies, and institutional
data-handling policies would apply **on top** of this pipeline.

## Honest limits of fuzzy matching

- Fuzzy matching **will make mistakes**. Name-similarity plus date-of-birth is a
  strong signal but not a unique identifier.
- Auto-merge is applied **only above a tuned confidence threshold**. Borderline
  pairs are routed to **hold-for-review** and are **never silently merged**,
  because a wrong merge in a real records system is a serious error that can
  conflate two different people.
- The thresholds are configurable (`config/rules.yaml`) and the precision/recall
  trade-off is reported against known ground truth so operators can tune for their
  own risk tolerance.

## Responsible-use notice

RecordBridge is demonstrated on synthetic data. **Using it on real student
records requires appropriate authorization, security controls, and compliance
review** (including, in the United States, FERPA obligations). The authors provide
this software "as is" under the MIT License and make no warranty of fitness for
any particular regulatory or operational use.
