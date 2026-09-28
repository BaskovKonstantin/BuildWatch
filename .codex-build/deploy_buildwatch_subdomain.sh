#!/bin/sh
set -eu

PUB=/home/kon/projects/buildwatch-public
FE="$PUB/frontend"
SRC_TAR=/tmp/bw-frontend-src.tar.gz

echo "=== free some disk ==="
docker builder prune -f >/dev/null || true
df -h / | tail -1

echo "=== unpack synced frontend source ==="
if [ -f "$SRC_TAR" ]; then
  rm -rf "$FE/app" "$FE/components" "$FE/lib" "$FE/public"
  mkdir -p "$FE"
  tar -xzf "$SRC_TAR" -C "$FE"
fi
cp -f /tmp/next.config.ts "$FE/next.config.ts" 2>/dev/null || true
cp -f /tmp/frontend.Dockerfile.public "$FE/Dockerfile" 2>/dev/null || true
# Never overwrite live compose from /tmp — it drops Zen auth mounts and .env wiring.


echo "=== node_modules from LAN frontend (has leaflet) ==="
rm -rf "$FE/node_modules"
docker cp buildwatch-frontend-1:/app/node_modules "$FE/node_modules"
test -f "$FE/node_modules/leaflet/package.json"
test -f "$FE/node_modules/next/package.json"
grep -q IconArrowUpRight "$FE/components/Icons.tsx"

echo "=== next build BASE_PATH empty ==="
rm -rf "$FE/.next-prod" "$FE/.next"
docker run --rm \
  -v "$FE:/app" \
  -w /app \
  -e BUILDWATCH_BASE_PATH= \
  -e BUILDWATCH_API_ORIGIN=http://api:8600 \
  -e NODE_ENV=production \
  node:22-alpine \
  /bin/sh -c 'node node_modules/next/dist/bin/next build'
test -f "$FE/.next-prod/BUILD_ID"
python3 - <<'PY'
import json
from pathlib import Path
manifest = Path('/home/kon/projects/buildwatch-public/frontend/.next-prod/routes-manifest.json')
data = json.loads(manifest.read_text())
print('basePath=', repr(data.get('basePath', '')))
if data.get('basePath'):
    raise SystemExit('basePath must be empty for subdomain deploy')
PY

echo "=== ensure compose mounts .next-prod and empty BASE_PATH ==="
python3 - <<'PY'
from pathlib import Path
p = Path('/home/kon/projects/buildwatch-public/docker-compose.public.yml')
text = p.read_text(encoding='utf-8')
text = text.replace('BUILDWATCH_BASE_PATH: /buildwatch', 'BUILDWATCH_BASE_PATH: ""')
text = text.replace('BUILDWATCH_BASE_PATH: /buildwatch', 'BUILDWATCH_BASE_PATH: ""')
if 'BUILDWATCH_BASE_PATH: ""' not in text and "BUILDWATCH_BASE_PATH: ''" not in text:
    text = text.replace('BUILDWATCH_BASE_PATH: /buildwatch', 'BUILDWATCH_BASE_PATH: ""')
# force empty in args/env via rewrite of known block
import re
text = re.sub(r'BUILDWATCH_BASE_PATH:\s*/buildwatch', 'BUILDWATCH_BASE_PATH: ""', text)
text = re.sub(r'BUILDWATCH_BASE_PATH:\s*""', 'BUILDWATCH_BASE_PATH: ""', text)
if './frontend/.next-prod:/app/.next-prod:ro' not in text:
    text = text.replace(
        '    volumes:\n      - ./frontend/public/moscow-schematic.svg:/app/public/moscow-schematic.svg:ro\n',
        '    volumes:\n      - ./frontend/.next-prod:/app/.next-prod:ro\n      - ./frontend/public/moscow-schematic.svg:/app/public/moscow-schematic.svg:ro\n',
    )
p.write_text(text, encoding='utf-8')
print('compose ok')
PY

cd "$PUB"
# Recreate frontend using existing image + new .next-prod mount; patch runtime env
docker compose -f docker-compose.public.yml up -d --no-build --force-recreate frontend
sleep 4

echo "=== local probes ==="
curl -sS -m 10 -o /dev/null -w 'ui_root=%{http_code}\n' http://127.0.0.1:8701/
curl -sS -m 10 -o /dev/null -w 'api=%{http_code}\n' http://127.0.0.1:8601/api/health
curl -sS -m 10 -H 'Host: buildwatch.baski.pro' -o /dev/null -w 'caddy_http_host=%{http_code}\n' http://127.0.0.1/
# HTTPS via local caddy with host
curl -sk -m 15 -H 'Host: buildwatch.baski.pro' -o /dev/null -w 'caddy_https_host=%{http_code}\n' https://127.0.0.1/
curl -sk -m 15 -H 'Host: buildwatch.baski.pro' https://127.0.0.1/api/health; echo

docker exec buildwatch-public-frontend-1 sh -c 'echo BASE=$BUILDWATCH_BASE_PATH; test -f /app/.next-prod/BUILD_ID && echo build_id_ok'
echo DONE
