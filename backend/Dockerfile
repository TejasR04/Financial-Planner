FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV" \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

FROM builder AS test-builder

COPY requirements-dev.txt .
RUN python -m pip install --no-cache-dir -r requirements-dev.txt

FROM python:3.12-slim AS production

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system meridian \
    && useradd --system --gid meridian --create-home meridian

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=meridian:meridian app ./app
COPY --chown=meridian:meridian alembic ./alembic
COPY --chown=meridian:meridian alembic.ini ./alembic.ini

USER meridian

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM production AS test

USER root
COPY --from=test-builder /opt/venv /opt/venv
COPY --chown=meridian:meridian tests ./tests
COPY --chown=meridian:meridian pyproject.toml ./pyproject.toml
USER meridian

FROM production AS runtime
