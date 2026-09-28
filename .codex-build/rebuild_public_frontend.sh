#!/bin/sh
set -eu
ROOT=/home/kon/projects/buildwatch-public
FE=$ROOT/frontend
docker run --rm -v "$FE:/app" alpine rm -rf /app/.next-prod /app/.next
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$FE:/app" \
  -w /app \
  -e BUILDWATCH_BASE_PATH= \
  -e BUILDWATCH_API_ORIGIN=http://api:8600 \
  -e NODE_ENV=production \
  -e HOME=/tmp \
  -e NEXT_TELEMETRY_DISABLED=1 \
  node:22-alpine \
  /bin/sh -c 'node node_modules/next/dist/bin/next build 2>&1 | tail -12 && test -f .next-prod/BUILD_ID && echo BUILD_OK'
cd "$ROOT"
docker compose -f docker-compose.public.yml up -d --force-recreate frontend
sleep 5
docker compose -f docker-compose.public.yml ps frontend
curl -sS -m 10 -o /dev/null -w "local=%{http_code}\n" http://127.0.0.1:8701/objects/7
