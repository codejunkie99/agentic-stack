FROM node:22-bookworm-slim
ARG CODEX_VERSION=0.153.2
ARG CLAUDE_VERSION=2.1.263
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 git ca-certificates openssh-client ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex@${CODEX_VERSION} @anthropic-ai/claude-code@${CLAUDE_VERSION} \
    && npm cache clean --force
WORKDIR /app
COPY harness_manager /app/harness_manager
COPY adapters /app/adapters
COPY .agent /app/.agent
COPY onboard*.py /app/
COPY LICENSE /app/LICENSE
COPY deploy/agentic-stack/healthcheck.py /app/healthcheck.py
COPY deploy/agentic-stack/sandbox-check.py /app/sandbox-check.py
RUN mkdir -p /data/projects /data/service /data/home \
    && chown -R node:node /data
ENV HOME=/data/home PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 AGENTIC_STACK_ROOT=/app
USER node
EXPOSE 8765
CMD ["python3", "-m", "harness_manager.cli", "serve", "--data-root", "/data/service", "--project-root", "/data/projects", "--host", "0.0.0.0", "--port", "8765", "--allow-network"]
