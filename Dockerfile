FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system appuser && useradd --system --gid appuser --create-home appuser

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]
