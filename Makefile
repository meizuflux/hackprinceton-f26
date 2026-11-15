.DEFAULT_GOAL := help
.PHONY: help frontend-install frontend-dev frontend-build frontend-test frontend-preview frontend-format \
	data-install data-generate data-verify data-truth backend-install backend-test backend-ingest-kestrel \
	backend-analyze-kestrel backend-serve backend-seed-kestrel backend-llm-record backend-demo-snapshot backend-chat-record dev \
	docker-up docker-down docker-logs

PYTHON ?= python3
UV ?= uv
GENERATOR := generator/generate.py
# Backend commands run in the uv project at backend/ (pyproject.toml + uv.lock), from backend/.
# --locked fails if uv.lock is out of date with pyproject.toml instead of silently re-resolving.
BACKEND_PY := $(UV) run --locked python
API ?= http://127.0.0.1:8000

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
	@echo "make backend-install   Sync backend/.venv from backend/uv.lock with uv (Python 3.12, dev group included)"
	@echo "make backend-test      Run backend tests, including a full Kestrel ingestion"
	@echo "make backend-ingest-kestrel  Ingest the Kestrel upload ZIP into backend/runs/kestrel/"
	@echo "make backend-analyze-kestrel Run the reasoning pipeline on backend/runs/kestrel/"
	@echo "make backend-serve     Start the API at http://127.0.0.1:8000"
	@echo "make backend-seed-kestrel  Upload the Kestrel ZIP to the running API and wait for analysis (API=...)"
	@echo "make backend-llm-record    Record Kestrel LLM responses into backend/llm_cache/ (billed; needs ANTHROPIC_API_KEY)"
	@echo "make backend-demo-snapshot Rebuild backend/demo/kestrel.tar.gz by replaying the cache (no API calls)"
	@echo "make backend-chat-record   Record answers to the Kestrel chat's suggested questions (billed; needs ANTHROPIC_API_KEY)"
	@echo "make dev               Start the API and Vite together (the frontend proxies /api to the API)"
	@echo "make docker-up         Build and start the backend and frontend containers at http://localhost:5173"
	@echo "make docker-down       Stop the containers (case data stays in the mapletrace-data volume)"
	@echo "make docker-logs       Follow the container logs"

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
	cd backend && $(UV) sync --locked

backend-test:
	cd backend && $(BACKEND_PY) -m pytest -q tests

backend-ingest-kestrel:
	cd backend && $(BACKEND_PY) -m mapletrace_ingest ingest ../cases/kestrel/kestrel_case_upload.zip --out runs/kestrel --overwrite

backend-analyze-kestrel:
	cd backend && $(BACKEND_PY) -m mapletrace_reason analyze runs/kestrel

backend-serve:
	cd backend && $(BACKEND_PY) -m uvicorn mapletrace_api.app:app --host 127.0.0.1 --port 8000

backend-seed-kestrel:
	@job=$$(curl -sf -F file=@cases/kestrel/kestrel_case_upload.zip -F case_name=Kestrel $(API)/upload \
		| $(PYTHON) -c "import json,sys; print(json.load(sys.stdin)['jobId'])") || \
		{ echo "Upload failed: is the API running? (make backend-serve)"; exit 1; }; \
	echo "Analysing Kestrel (job $$job)..."; \
	for i in $$(seq 1 120); do \
		status=$$(curl -sf $(API)/status/$$job | $(PYTHON) -c "import json,sys; j=json.load(sys.stdin); print(j['status'], j.get('caseId', ''))"); \
		case "$$status" in \
			ready*) echo "Ready: http://127.0.0.1:5173/cases/$${status#ready }"; exit 0;; \
			failed*) echo "Analysis failed; see GET $(API)/status/$$job"; exit 1;; \
		esac; \
		sleep 1; \
	done; echo "Timed out waiting for analysis"; exit 1

dev:
	$(MAKE) -j2 backend-serve frontend-dev

backend-llm-record:
	cd backend && $(BACKEND_PY) -m mapletrace_api.demo record

backend-demo-snapshot:
	cd backend && $(BACKEND_PY) -m mapletrace_api.demo snapshot

DOCKER_COMPOSE ?= docker compose

docker-up:
	$(DOCKER_COMPOSE) up --build -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f

backend-chat-record:
	cd backend && $(BACKEND_PY) -m mapletrace_api.chat record
