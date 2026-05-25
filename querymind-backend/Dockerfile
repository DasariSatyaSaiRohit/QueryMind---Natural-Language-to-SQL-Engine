FROM python:3.12-slim

# System dependencies for cryptography + psycopg2 + mysqlclient builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create non-root user for security
RUN addgroup --system querymind && adduser --system --ingroup querymind querymind
USER querymind

EXPOSE 8001

# Default command: run the FastAPI server.
# Override with "celery -A workers.celery_app.celery_app worker ..." for workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
