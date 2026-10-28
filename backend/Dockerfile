# Stage 1: Build & Runtime for Python FastAPI Backend
FROM python:3.12-slim

# System dependencies for OpenCV, PyAV, FFmpeg, and media processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY backend/requirements.txt ./backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt && \
    pip install --no-cache-dir alembic psycopg2-binary

# Copy application source code and models
COPY backend/ ./backend/
COPY datasets/ ./datasets/
COPY docs/ ./docs/
COPY alembic.ini ./alembic.ini

# Ensure storage directories exist
RUN mkdir -p /app/storage/recordings /app/storage/audio /app/storage/resumes /app/storage/reports

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATABASE_URL=sqlite:////app/storage/pluto.db

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

