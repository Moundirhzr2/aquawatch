FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DBT_SEND_ANONYMOUS_USAGE_STATS=false
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir -c requirements.lock '.[analytics]' \
    && useradd --create-home --uid 10001 aquawatch
COPY dbt ./dbt
COPY scripts ./scripts
COPY powerbi ./powerbi
RUN mkdir -p runtime dbt/target dbt/logs dbt/seeds && chown -R aquawatch:aquawatch /app
USER aquawatch
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "aquawatch.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
