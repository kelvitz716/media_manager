# Use Python 3.12 slim base image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    gettext-base && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Create necessary directories and set permissions
RUN mkdir -p /app/temp_downloads /app/logs && \
    chmod +x /app/scripts/docker_entrypoint.sh /app/scripts/init_config.py && \
    mkdir -p /app/.sessions && \
    chown -R nobody:nogroup /app/temp_downloads /app/logs /app/.sessions /app && \
    chmod -R 777 /app/temp_downloads /app/logs /app/.sessions && \
    touch /app/config.json && \
    chown nobody:nogroup /app/config.json && \
    chmod 666 /app/config.json

# Switch to non-root user
USER nobody

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/app/config.json
ENV PYTHONPATH=/app

# Set entrypoint
ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]