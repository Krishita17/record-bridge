# RecordBridge Makefile
# Run `make help` for the list of targets.

PYTHON ?= python
SEED   ?= 42
N      ?= 5000
RATE   ?= 0.15
DB     ?= data/recordbridge.db
CONFIG ?= config/rules.yaml
INPUT  ?= data/students_raw_intake.csv

.PHONY: help setup data run ingest validate dedupe load evaluate report figures dashboard all test lint clean

help:
	@echo "RecordBridge targets:"
	@echo "  make setup      Create venv and install (editable)"
	@echo "  make data       Generate synthetic data + ground truth"
	@echo "  make run        Ingest -> validate -> dedupe -> correct/audit -> load"
	@echo "  make evaluate   Accuracy vs ground truth (precision/recall)"
	@echo "  make report     Exception report + audit-trail excerpt"
	@echo "  make figures    Regenerate all README figures"
	@echo "  make dashboard  Build the interactive Plotly dashboard"
	@echo "  make all        Full reproducible end-to-end flow"
	@echo "  make test       Run the test suite"
	@echo "  make clean      Remove generated data/figures/reports/db"

setup:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -e .
	@echo "Activate with: source .venv/bin/activate"

data:
	$(PYTHON) -m recordbridge.cli data --n $(N) --error-rate $(RATE) --seed $(SEED) --out data

# `run` performs ingest -> validate -> dedupe -> correct/audit -> load as one
# governed transaction. The aliases below exist so each stage is nameable.
run:
	$(PYTHON) -m recordbridge.cli run --input $(INPUT) --config $(CONFIG) --db $(DB)

ingest validate dedupe load: run

evaluate:
	$(PYTHON) -m recordbridge.cli evaluate --db $(DB) --data data --out results

report:
	$(PYTHON) -m recordbridge.cli report --db $(DB)

figures:
	$(PYTHON) -m recordbridge.cli figures --db $(DB) --data data --out figures

dashboard:
	$(PYTHON) -m recordbridge.cli dashboard --db $(DB) --data data

all:
	$(PYTHON) -m recordbridge.cli all --n $(N) --error-rate $(RATE) --seed $(SEED)

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m pyflakes src/recordbridge || true

clean:
	rm -f data/*.csv data/*.db figures/*.png reports/*.md results/*.json \
	      dashboard/*.html
	@echo "Cleaned generated artifacts."
