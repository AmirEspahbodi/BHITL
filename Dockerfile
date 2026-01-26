# # pull official base image
FROM python:3.14-slim AS python-base

# Define application directory and user
ENV APP_HOME=/home/python_user
ENV APP_USER=python_user

RUN adduser --disabled-password --gecos "" $APP_USER
RUN chown -R $APP_USER:$APP_USER $APP_HOME

WORKDIR $APP_HOME

# Set timezone and install tzdata
ENV TZ='Asia/Tehran'
RUN echo $TZ > /etc/timezone && apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    rm -f /etc/localtime && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set environment variables to optimize Python runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=$APP_HOME

# Poetry environment variables
ENV POETRY_VERSION=2.2.1
ENV POETRY_HOME=$APP_HOME/poetry
ENV POETRY_VENV=/opt/poetry-venv

# --- CHANGE START ---
# Move the cache and virtualenvs OUTSIDE of APP_HOME so the volume mount doesn't hide them
ENV POETRY_CACHE_DIR=/opt/poetry-cache
ENV POETRY_VIRTUALENVS_PATH=/opt/poetry-venvs
# --- CHANGE END ---

# Upgrade pip
RUN pip install --upgrade pip

# --- CHANGE START ---
# Create all necessary directories and assign permissions
RUN mkdir -p $POETRY_VENV $POETRY_CACHE_DIR $POETRY_VIRTUALENVS_PATH && \
    chown -R $APP_USER:$APP_USER $POETRY_VENV $POETRY_CACHE_DIR $POETRY_VIRTUALENVS_PATH
# --- CHANGE END ---

# Switch to non-root user for added security
USER $APP_USER

# ------------------------------------------------------------------
# Stage: Poetry Environment Setup
# ------------------------------------------------------------------
FROM python-base AS poetry-base

# Create a virtual environment for Poetry and install it
RUN python3 -m venv $POETRY_VENV && \
    $POETRY_VENV/bin/pip install --upgrade pip setuptools && \
    $POETRY_VENV/bin/pip install poetry==$POETRY_VERSION

# ------------------------------------------------------------------
# Stage: Application Dependency Installation
# ------------------------------------------------------------------
FROM python-base AS example-app-base

# Copy Poetry virtual environment from previous stage
COPY --from=poetry-base ${POETRY_VENV} ${POETRY_VENV}

# Add Poetry to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

# Copy dependency files with proper ownership
COPY --chown=$APP_USER:$APP_USER pyproject.toml README.md $APP_HOME/

# Validate project configuration
RUN poetry check

# Install project dependencies
# (without installing the project package itself)
RUN poetry install --no-interaction --no-cache --no-root

# ------------------------------------------------------------------
# Stage: Final Application Image
# ------------------------------------------------------------------
FROM example-app-base AS example-app-final

# Copy application source code with proper ownership
COPY --chown=$APP_USER:$APP_USER app/ $APP_HOME/app/
COPY --chown=$APP_USER:$APP_USER scripts/ $APP_HOME/scripts/
COPY --chown=$APP_USER:$APP_USER alembic.ini $APP_HOME/alembic.ini
COPY --chown=$APP_USER:$APP_USER principles.json $APP_HOME/principles.json
COPY --chown=$APP_USER:$APP_USER samples.json $APP_HOME/samples.json

# Ensure scripts are executable (Note: Volume mount will override this, ensure local scripts are +x)
RUN chmod +x $APP_HOME/scripts/*

# Switch to non-root user
USER $APP_USER

# Expose internal port
EXPOSE 3000

# # Health check
# HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
#     CMD curl -f http://localhost:3000/health || exit 1

# # Run the application with uvicorn
# CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--workers", "2", "--log-level", "info"]
