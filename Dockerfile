FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY project_robots.py .
COPY robots/ robots/
RUN pip install --no-cache-dir --prefix=/install -e .

FROM python:3.11-slim AS runner
WORKDIR /app
RUN addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /app appuser \
    && chown -R appuser:appgroup /app
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup pyproject.toml .
COPY --chown=appuser:appgroup project_robots.py .
COPY --chown=appuser:appgroup robots/ robots/
USER appuser
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -m pytest -q --collect-only || exit 1
CMD ["python", "project_robots.py", "--help"]
