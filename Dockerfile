# Recruitment Assistant backend (CrewAI + FastAPI).
# Build context: repository root. Python 3.13 — crewai/fastapi wheels are not
# published for 3.14 as of this MVP (see backend.md Assumptions).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CREWAI_TELEMETRY_OPT_OUT=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
RUN mkdir -p /app/project-context/2.build/logs

WORKDIR /app/backend
EXPOSE 8000

# Bind all interfaces inside the container. Secrets come from compose/env_file
# or `--env-file` at run time — never baked into the image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
