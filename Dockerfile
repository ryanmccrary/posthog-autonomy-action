FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# GitHub Actions overrides WORKDIR to /github/workspace, so set PYTHONPATH
# to ensure the src package is always importable
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "-m", "src.main"]
