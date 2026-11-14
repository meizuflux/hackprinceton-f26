.DEFAULT_GOAL := help
.PHONY: help frontend-install frontend-dev frontend-build frontend-test frontend-preview frontend-format \
	data-install data-generate data-verify data-truth backend-install backend-test backend-ingest-kestrel

PYTHON ?= python3
UV ?= uv
GENERATOR := generator/generate.py

help:
	@echo "make frontend-install  Install locked dependencies"
	@echo "make frontend-dev      Start Vite at http://localhost:5173"
	@echo "make frontend-build    Build the frontend into frontend/dist/"
	@echo "make frontend-test     Run contract tests"
	@echo "make frontend-preview  Preview the production build"
	@echo "make frontend-format   Format source files"
	@echo "make data-install      Install generator dependencies with uv (UV=uv)"
	@echo "make data-generate     Regenerate the synthetic Kestrel case in cases/kestrel/"
	@echo "make data-verify       Rebuild the case in a temp dir and check every file hash"
	@echo "make data-truth        Write the answer key to .truth/kestrel/ (git-ignored; scoring only)"
	@echo "make backend-install   Install backend ingestion dependencies (PYTHON=python3)"
	@echo "make backend-test      Run backend tests, including a full Kestrel ingestion"
	@echo "make backend-ingest-kestrel  Ingest the Kestrel upload ZIP into backend/runs/kestrel/"

frontend-install:
	cd frontend && bun install --frozen-lockfile

frontend-dev:
	cd frontend && bun run --bun dev --host 127.0.0.1 --port 5173 --strictPort

frontend-build:
	cd frontend && bun run --bun build

frontend-test:
	cd frontend && bun run --bun test

frontend-preview:
	cd frontend && bun run --bun preview --host 127.0.0.1

frontend-format:
	cd frontend && bun run --bun format

data-install:
	$(UV) sync --locked --script $(GENERATOR)

data-generate:
	$(UV) run --locked --script $(GENERATOR)

data-verify:
	$(UV) run --locked --script $(GENERATOR) --verify

data-truth:
	$(UV) run --locked --script $(GENERATOR) --truth-out .truth/kestrel

backend-install:
	$(PYTHON) -m pip install -r backend/requirements.txt

backend-test:
	cd backend && $(PYTHON) -m pytest -q tests

backend-ingest-kestrel:
	cd backend && $(PYTHON) -m compstat_ingest ingest ../cases/kestrel/kestrel_case_upload.zip --out runs/kestrel --overwrite
