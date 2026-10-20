FROM ghcr.io/astral-sh/uv:0.11.18 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONPATH=/app/apps/api PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY apps/api ./apps/api
COPY scripts/seed_supervisor_demo.py ./scripts/seed_supervisor_demo.py
COPY datasets/synthetic_project/scope.md ./datasets/synthetic_project/scope.md
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
