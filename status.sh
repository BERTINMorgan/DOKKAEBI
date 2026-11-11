#!/usr/bin/env bash
# DOKKÆBI — affiche l'état des conteneurs, les URLs utiles et teste l'API.
set -uo pipefail
cd "$(dirname "$0")"

echo "==> Conteneurs:"
docker compose ps
echo
echo "==> Test API interne (backend):"
curl -s --max-time 3 http://127.0.0.1:8080/api/health && echo "  ← OK" || echo "  ← ÉCHEC (backend injoignable via le proxy web)"
echo
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "==> URLs:"
echo "    Interface web (ce PC)   : http://127.0.0.1:8080"
echo "    Interface web (réseau)  : http://${IP:-<ip>}:8080   (depuis téléphone/PC du même WiFi)"
echo "    MQTT pour les ESP32     : ${IP:-<ip>}:1883  (topic dokkaebi/#)"
echo "    NAS Samba               : smb://${IP:-<ip>}/dokkaebi  (user: dokkaebi / pass: dokkaebi)"
echo
echo "==> Derniers logs (20 lignes):"
docker compose logs --tail=20
