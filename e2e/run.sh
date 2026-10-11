#!/usr/bin/env bash
# Runs the browser test against a running stack and regenerates docs/images/*.png.
#
#   docker compose up -d --build --wait       # the stack must be up (demo mode needs no API key)
#   bash e2e/run.sh                           # BASE_URL defaults to the stack's published port
#
# It drives a real Chromium (Playwright, in Docker) through the whole user journey and asserts as it goes, so it
# is a test first and a screenshot tool second. The first run pulls the Playwright image (about 2 GB).
#
# Note: every run uploads three documents, and the API allows 10 uploads per client per 10 minutes. Running it
# repeatedly needs `docker compose restart backend` in between (the limiter lives in memory).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PORT="${FRONTEND_PORT:-8082}"
PLAYWRIGHT_VERSION="1.58.2"

# `pwd -W` gives a Windows path under Git Bash; elsewhere plain pwd is right.
abs() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

mkdir -p "$ROOT/docs/images"

# The test folder is mounted read-only and copied inside the container, so npm installs Playwright there and
# leaves nothing (node_modules, package.json) behind in the repository.
inside_container="mkdir /work && cp /src/e2e.mjs /work/ && cd /work \
  && npm init -y >/dev/null 2>&1 \
  && npm i playwright@${PLAYWRIGHT_VERSION} --silent --no-audit --no-fund \
  && node e2e.mjs"

MSYS_NO_PATHCONV=1 docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e BASE_URL="${BASE_URL:-http://host.docker.internal:$PORT}" \
  -v "$(abs "$HERE"):/src:ro" \
  -v "$(abs "$ROOT/docs/images"):/out" \
  -v "$(abs "$ROOT/backend/evals/dataset/dev"):/data:ro" \
  "mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-jammy" \
  sh -c "$inside_container"
