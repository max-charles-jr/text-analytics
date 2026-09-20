# CLD-410 text-analytics Django app
# Base: slim CPython image, pinned minor version for reproducibility.
FROM python:3.12-slim

# Prevents Python from buffering stdout/stderr, so `docker logs` / CloudWatch
# Logs show output immediately instead of on buffer flush.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=textlab.settings \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the NLTK models/corpora at BUILD time, not at container
# startup. This means (a) the running container needs no outbound internet
# access to nltk.org at runtime -- important once the ECS task is locked
# down to an internal security group -- and (b) the first request isn't
# slowed down by a multi-megabyte download.
RUN python -m nltk.downloader -d /usr/local/share/nltk_data \
    punkt punkt_tab averaged_perceptron_tagger averaged_perceptron_tagger_eng \
    maxent_ne_chunker maxent_ne_chunker_tab words

COPY . .

# Run as a non-root user inside the container (least privilege).
RUN useradd --no-create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1

# 2 gunicorn workers is enough for a 0.5 vCPU / 1GB Fargate task; tune via
# the WEB_CONCURRENCY env var if the task size changes later.
CMD ["gunicorn", "textlab.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
