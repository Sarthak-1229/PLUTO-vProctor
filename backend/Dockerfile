# Production Runtime for Python FastAPI Backend
FROM python:3.12-slim

# System dependencies for OpenCV, PyAV, FFmpeg, audio analysis and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 1000 pluto && \
    useradd -u 1000 -g pluto -m -s /bin/bash pluto

WORKDIR /app

# Copy dependency requirements
COPY backend/requirements.txt ./backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy application source code, datasets, documentation and database migrations
COPY backend/ ./backend/
COPY datasets/ ./datasets/
COPY docs/ ./docs/
COPY alembic.ini ./alembic.ini

# Ensure storage directories exist with correct non-root permissions
RUN mkdir -p /app/storage/recordings /app/storage/audio /app/storage/resumes /app/storage/reports /app/backend/app/data/processed && \
    chown -R pluto:pluto /app

USER pluto

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATABASE_URL=sqlite:////app/storage/pluto.db

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
