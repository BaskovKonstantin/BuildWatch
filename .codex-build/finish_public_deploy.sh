#!/bin/sh
set -eu
PUB=/home/kon/projects/buildwatch-public

docker rm -f mcopy-lan mcopy-pub 2>/dev/null || true
docker create --name mcopy-lan -v buildwatch_buildwatch-media:/data alpine
rm -rf /tmp/bw-media-sync
mkdir -p /tmp/bw-media-sync
docker cp mcopy-lan:/data/. /tmp/bw-media-sync/
docker rm mcopy-lan
docker create --name mcopy-pub -v buildwatch-public_buildwatch-media:/data alpine
docker cp /tmp/bw-media-sync/. mcopy-pub:/data/
docker rm mcopy-pub
du -sh /tmp/bw-media-sync

cd "$PUB"
docker compose -f docker-compose.public.yml build api
docker compose -f docker-compose.public.yml up -d api worker
sleep 4

curl -sS -m 15 http://127.0.0.1:8601/api/health; echo
curl -sS -m 15 http://127.0.0.1:8601/api/assistant/status; echo
curl -sS -m 15 http://127.0.0.1:8601/api/objects | python3 -c 'import sys,json; print("objects", len(json.load(sys.stdin)))'

cp -f /tmp/bw-deploy-sync/.codex-build/deploy_buildwatch_subdomain.sh /tmp/deploy_buildwatch_subdomain.sh
chmod +x /tmp/deploy_buildwatch_subdomain.sh
sh /tmp/deploy_buildwatch_subdomain.sh

curl -sk -m 15 -H 'Host: buildwatch.baski.pro' https://127.0.0.1/api/health; echo
curl -sk -m 15 -H 'Host: buildwatch.baski.pro' https://127.0.0.1/api/assistant/status; echo
