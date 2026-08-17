# syntax=docker/dockerfile:1.7

# ---- Builder ----------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml setup.py requirements.txt ./
COPY src ./src

RUN python -m pip install --upgrade pip build \
 && python -m build --wheel --outdir /dist

# ---- Runtime ------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="mcp-data-tools" \
      org.opencontainers.image.description="Governed MCP server for BigQuery, GCS, Airflow, and data-quality operations" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_DATA_TOOLS_CONFIG=/etc/mcp-data-tools/config.yaml

# Non-root runtime user (defense in depth: this process handles credentials).
RUN groupadd --system --gid 10001 mcpdt \
 && useradd --system --uid 10001 --gid mcpdt --create-home --shell /usr/sbin/nologin mcpdt

WORKDIR /app

COPY --from=builder /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
 && rm -rf /tmp/*.whl

COPY configs/default.yaml /etc/mcp-data-tools/config.yaml

USER mcpdt

ENTRYPOINT ["mcp-data-tools"]
CMD ["serve", "--config", "/etc/mcp-data-tools/config.yaml"]
