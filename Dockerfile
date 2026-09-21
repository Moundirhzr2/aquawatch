FROM python:3.12-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DBT_SEND_ANONYMOUS_USAGE_STATS=false
# Apply Debian security updates, including fixes absent from the published base.
# Fail the build if the five Snyk PR #9 findings could still be present.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' perl-base)" ge '5.40.1-6+deb13u1' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libpcre2-8-0)" ge '10.46-1~deb13u2' \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml requirements.lock requirements-container.txt ./
COPY src ./src
# pip is build tooling; remove it and its vendored dependencies from runtime.
RUN python -m pip install --no-cache-dir --only-binary :all: --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir --only-binary :all: -c requirements.lock -r requirements-container.txt '.[analytics]' \
    && python -m pip uninstall --yes pip \
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
