# 中継（graph_mcp_gateway）と Open WebUI の初期設定のイメージ。
# runtime 段：本番で動かす。test 段：単体・結合テストと E2E の実行役、模擬の起動に使う。
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.14.10-slim AS base
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN useradd --uid 10001 --create-home app && mkdir -p /data && chown app /data

FROM base AS runtime
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY external/open-webui/src ./external/open-webui/src
RUN uv sync --frozen --no-dev --no-editable
ENV FASTMCP_HOME=/data
USER app
EXPOSE 8000
CMD ["python", "-m", "graph_mcp_gateway"]

FROM base AS test
RUN uv sync --frozen --no-install-project
COPY src ./src
COPY external/open-webui/src ./external/open-webui/src
RUN uv sync --frozen --no-editable
ENV FASTMCP_HOME=/data
USER app
CMD ["pytest", "tests"]
