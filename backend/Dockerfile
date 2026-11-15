# MapleTrace API. Build from the repository root (compose.yaml does this):
#   docker build -f backend/Dockerfile .
# The image mirrors the repository layout under /app so the demo restore path in
# mapletrace_api/app.py (REPO / "cases" / "kestrel" / "kestrel_case_upload.zip") resolves unchanged:
#   /app/backend/{mapletrace_api,mapletrace_ingest,mapletrace_reason,demo,llm_cache}
#   /app/cases/kestrel/kestrel_case_upload.zip
FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

COPY --from=uv /uv /usr/local/bin/uv

COPY backend/requirements.txt /app/backend/requirements.txt
RUN uv venv /opt/venv && uv pip install --python /opt/venv/bin/python -r /app/backend/requirements.txt

# Case data (uploads, ingestion runs, analysis versions, jobs) lives on a volume owned by the
# non-root user. Code, the demo snapshot and the recorded LLM cache stay root-owned and read-only.
RUN useradd --system --uid 10001 --create-home --home-dir /home/mapletrace mapletrace \
    && mkdir -p /data \
    && chown mapletrace:mapletrace /data

COPY backend/mapletrace_api /app/backend/mapletrace_api
COPY backend/mapletrace_ingest /app/backend/mapletrace_ingest
COPY backend/mapletrace_reason /app/backend/mapletrace_reason
COPY backend/demo /app/backend/demo
COPY backend/llm_cache /app/backend/llm_cache
COPY cases/kestrel/kestrel_case_upload.zip /app/cases/kestrel/kestrel_case_upload.zip

ENV MAPLETRACE_DATA=/data \
    MAPLETRACE_MAX_UPLOAD_MB=100
VOLUME ["/data"]

WORKDIR /app/backend
USER mapletrace
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["uvicorn", "mapletrace_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
