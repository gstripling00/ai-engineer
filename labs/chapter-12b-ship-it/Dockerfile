# Aegis as a container. Build from the repo root so the chapter folders are in context:
#   docker build -f labs/chapter-12b-ship-it/Dockerfile -t aegis:dev .
#   docker run --rm -p 8000:8000 -e AEGIS_MODEL=mock aegis:dev
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# ONE requirements file, same as every lab and CI.
COPY requirements.txt .
RUN pip install --no-warn-conflicts -r requirements.txt

# The service imports Chapters 10 and 13 from their own folders.
COPY labs/chapter-10-evaluation-and-observability labs/chapter-10-evaluation-and-observability
COPY labs/chapter-13-assembling-aegis labs/chapter-13-assembling-aegis
COPY labs/chapter-06-rag-grounding-aegis labs/chapter-06-rag-grounding-aegis
COPY labs/chapter-12b-ship-it labs/chapter-12b-ship-it

# Run as a non-root user. Keys arrive as environment variables at run time, never baked in.
RUN useradd --create-home aegis && chown -R aegis:aegis /app
USER aegis

ENV AEGIS_MODEL=mock AEGIS_TIMEOUT_S=10 AEGIS_RATE_LIMIT_PER_MIN=120
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"

WORKDIR /app/labs/chapter-12b-ship-it
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
