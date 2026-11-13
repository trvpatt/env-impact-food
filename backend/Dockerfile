# Build stage of build/release/run: code + dependencies only. Config is injected at release via env vars.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini .

RUN useradd --create-home rooted
USER rooted

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
