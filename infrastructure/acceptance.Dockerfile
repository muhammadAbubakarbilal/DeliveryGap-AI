FROM ghcr.io/astral-sh/uv:0.11.18 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONPATH=/app/apps/api:/app/apps/api/tests PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY alembic.ini ./
COPY apps/api ./apps/api
RUN useradd --uid 10001 --create-home app && chown -R app:app /app
USER app
CMD ["/app/.venv/bin/python", "-m", "pytest", "-q", "apps/api/tests/test_infrastructure_acceptance.py"]
