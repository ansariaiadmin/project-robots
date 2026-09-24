FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY project_robots.py .
COPY robots/ robots/
RUN pip install --no-cache-dir -e .
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -m pytest -q --collect-only || exit 1
CMD ["python", "project_robots.py", "--help"]
