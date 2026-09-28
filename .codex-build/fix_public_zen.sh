#!/bin/sh
set -eu
PUB=/home/kon/projects/buildwatch-public
COMPOSE_SRC=/tmp/bw-deploy-sync/.codex-build/docker-compose.public.yml

cp -f "$COMPOSE_SRC" "$PUB/docker-compose.public.yml"

python3 <<'PY'
import json
import os
from pathlib import Path

auth_path = Path("/home/kon/.local/share/opencode/auth.json")
env_path = Path("/home/kon/projects/buildwatch-public/.env")
key = os.environ.get("BUILDWATCH_ZEN_KEY")
if not key and auth_path.is_file():
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    for provider in ("opencode", "opencode-go"):
        cred = auth.get(provider) or {}
        if cred.get("key"):
            key = cred["key"]
            break
if key:
    env_path.write_text(
        f"BUILDWATCH_ZEN_KEY={key}\nBUILDWATCH_ZEN_MODEL=glm-5.3-flash\n",
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)
    print("zen_env=written")
else:
    print("zen_env=missing_key")
PY

cd "$PUB"
docker compose -f docker-compose.public.yml up -d --force-recreate api
sleep 3
curl -sS http://127.0.0.1:8601/api/assistant/status; echo
