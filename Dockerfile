# syntax=docker/dockerfile:1
FROM python:3.10-slim

WORKDIR /app

# 1. FIX: Upgrade existing system packages to clear OS-level vulnerabilities
# 2. FIX: Keep libpq-dev (runtime database communication library) but drop gcc in the next steps if possible
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./
# FIX: Upgrade pip during build to clear pip-level vulnerabilities
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the API port
EXPOSE 8000

# FIX: Switch to a non-root user so vulnerabilities cannot access the root filesystem
RUN useradd -m agentuser && chown -R agentuser:agentuser /app
USER agentuser

# Entrypoint for the FastAPI backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]