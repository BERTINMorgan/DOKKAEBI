#!/usr/bin/env bash
# ============================================================================
# DOKKÆBI — démarre toute la stack locale (Mosquitto + backend + web + NAS).
#
# Usage :
#   ./start.sh          → démarre tout (build si besoin)
#   ./start.sh --sim    → démarre + le simulateur de capteurs (démo sans ESP32)
#   ./stop.sh           → arrête tout
#   ./status.sh         → état des conteneurs + URLs + test API
#
# Prérequis : docker + plugin compose installés, et ton utilisateur dans le
# groupe docker (sinon lance avec sudo, ou fais: newgrp docker)
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERREUR: docker absent. Installe-le: sudo apt install docker.io docker-compose-plugin"
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "ERREUR: plugin 'docker compose' absent. Installe-le: sudo apt install docker-compose-plugin"
    exit 1
fi

echo "==> Préchargement des images (si déjà faites, c'est instantané)..."
docker compose pull || true
echo "==> Build des images locales (backend, web)..."
docker compose build

echo "==> Démarrage..."
if [ "${1:-}" = "--sim" ]; then
    docker compose --profile sim up -d
else
    docker compose up -d
fi

sleep 3
echo
./status.sh
