#!/bin/sh
set -e
cd /home/kon/projects/buildwatch-public
if ! grep -q 'backend/forecast.py' docker-compose.public.yml; then
  sed -i 's#^\(\s*\)- ./backend/rules.py:/app/backend/rules.py:ro#&\n\1- ./backend/forecast.py:/app/backend/forecast.py:ro#' docker-compose.public.yml
fi
grep -n 'backend/forecast.py' docker-compose.public.yml
docker compose -f docker-compose.public.yml up -d api
sleep 8
curl -s -m 15 http://127.0.0.1:8601/api/objects/7 | grep -o '"headline":"[^"]*"' | head -1
echo DEPLOY_OK
