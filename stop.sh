#!/usr/bin/env bash
# DOKKÆBI — arrête toute la stack (les données restent dans le volume docker).
set -euo pipefail
cd "$(dirname "$0")"
docker compose --profile sim down
echo "Stack arrêtée. Redémarrage: ./start.sh"
