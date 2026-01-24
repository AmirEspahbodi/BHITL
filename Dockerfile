FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1001 appuser && \
    chown -R appuser:appuser /app

# Copy pyproject.toml
COPY --chown=appuser:appuser pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application code
COPY --chown=appuser:appuser ./app ./app

COPY --chown=$APP_USER:$APP_USER app/ $APP_HOME/app/
COPY --chown=$APP_USER:$APP_USER scripts/ $APP_HOME/scripts/
COPY --chown=$APP_USER:$APP_USER alembic.ini $APP_HOME/alembic.ini

# Switch to non-root user
USER appuser

# Expose internal port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run the application with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--workers", "2", "--log-level", "info"]
