# pull official base image
FROM python:3.14.2-slim AS python-base


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

# Poetry environment variables (fixed typo)
ENV POETRY_VERSION=2.1.1
ENV POETRY_HOME=$APP_HOME/poetry
ENV POETRY_VENV=$APP_HOME/poetry-venv
ENV POETRY_CACHE_DIR=$APP_HOME/.poetry-cache

# Upgrade pip
RUN pip install --upgrade pip

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
COPY --chown=$APP_USER:$APP_USER ./pyproject.toml ./README.md $APP_HOME/

# Validate project configuration
RUN poetry check

# Install project dependencies (without installing the project package itself)
RUN poetry install --no-interaction --no-cache --no-root

# ------------------------------------------------------------------
# Stage: Final Application Image
# ------------------------------------------------------------------
FROM example-app-base AS example-app-final

# Copy application source code with proper ownership
COPY --chown=$APP_USER:$APP_USER app/ $APP_HOME/app/
COPY --chown=$APP_USER:$APP_USER scripts/ $APP_HOME/scripts/
COPY --chown=$APP_USER:$APP_USER alembic.ini $APP_HOME/alembic.ini

EXPOSE 8000
