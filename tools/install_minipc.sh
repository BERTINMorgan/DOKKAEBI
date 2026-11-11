#!/usr/bin/env bash
# ============================================================================
# DOKKÆBI — installation automatique du mini PC (à lancer UNE fois, à
# l'atelier, avec Internet). À faire en tant qu'utilisateur sudo.
#
# Usage :
#   sudo bash install_minipc.sh https://github.com/<ton-compte>/dokkaebi.git
#
# Ce que ça fait :
#   1. installe Docker + git
#   2. télécharge le projet Dokkaebi dans /opt/dokkaebi
#   3. précharge les images Docker (nécessite Internet, une seule fois)
#   4. démarre la stack (mosquitto + backend + web + nas)
# Ensuite, dans le van (hors ligne) : cd /opt/dokkaebi && docker compose up -d
# ============================================================================
set -euo pipefail

REPO_URL="${1:-https://github.com/EXEMPLE/dokkaebi.git}"
INSTALL_DIR="${2:-/opt/dokkaebi}"

echo "==> [1/5] Mise à jour du système et installation de Docker + git..."
apt-get update -y
apt-get install -y docker.io docker-compose-plugin git ca-certificates
systemctl enable --now docker

# L'utilisateur courant rejoint le groupe docker (évite de devoir faire sudo partout)
if [ -n "${SUDO_USER:-}" ]; then
    usermod -aG docker "$SUDO_USER"
    echo "==> NOTE : déconnecte-toi / reconnecte-toi (ou 'newgrp docker') pour activer le groupe docker."
fi

echo "==> [2/5] Téléchargement du projet dans $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
if [ -d .git ]; then
    git pull
else
    git clone "$REPO_URL" .
fi

echo "==> [3/5] Préchargement des images Docker (Internet requis, une seule fois)..."
docker compose pull || true          # images du hub (mosquitto, nginx, samba)
docker compose build                  # images locales (backend, web, sim)

echo "==> [4/5] Démarrage de la stack..."
docker compose up -d

echo "==> [5/5] Vérification..."
sleep 3
docker compose ps
echo
IP=$(hostname -I | awk '{print $1}')
echo "OK ! Interface web :  http://$IP:8080"
echo "MQTT (ESP32)      :  $IP:1883"
echo "NAS (Samba)       :  smb://$IP/dokkaebi  (user: dokkaebi / pass: dokkaebi — À CHANGER)"
echo
echo "Simulateur de capteurs (démo) :  docker compose --profile sim up -d sim"
echo "Logs :                            docker compose logs -f"
echo "Arrêt :                          docker compose down"
