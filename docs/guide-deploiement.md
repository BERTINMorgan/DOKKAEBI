# Guide de déploiement DOKKÆBI — version "zéro compétence informatique requise"

Ce guide te prend par la main, de l'achat du mini PC jusqu'à l'interface qui tourne dans le van.
Chaque étape = copier-coller des commandes. Aucune connaissance préalable n'est nécessaire.

---

## ÉTAPE 0 — Recevoir les fichiers du projet

Le projet complet (~20 fichiers) est poussé sur un dépôt GitHub privé (demande-moi de le faire
si ce n'est pas encore fait). Toi, tu as juste à :

1. Créer un compte sur https://github.com (gratuit).
2. Créer un dépôt (repo) privé, par ex. `dokkaebi`, et me donner son adresse
   (`https://github.com/<ton-compte>/dokkaebi`).
3. Sur le mini PC (une fois Ubuntu installé), tout se résume à UNE commande :

```bash
git clone https://github.com/<ton-compte>/dokkaebi.git /opt/dokkaebi
```

Alternative sans git : sur github.com, bouton vert **Code → Download ZIP**, dézipper sur une clé USB,
copier le dossier `dokkaebi` sur le mini PC.

---

## ÉTAPE 1 — Acheter le matériel

| Rôle | Quoi acheter | Budget indicatif |
|---|---|---|
| Mini PC (serveur + NAS) | **Lenovo ThinkCentre M720q Tiny** reconditionné (i3-8100T/9100T, 8 Go RAM, 256 Go SSD) — chercher sur BackMarket, Recommerce, Amazon Renewed. Alternative neuf : mini PC **Intel N100** (Beelink S12, MINISFORUM) | 150–250 € |
| Alim 12 V du van | Convertisseur DC-DC **12 V → 19 V** (si le mini PC est en 19 V, type Lenovo) avec fusible 10 A, ou alimentation PicoPSU si PC au format ATX | 20–40 € |
| Câble/connectique | Câble 12 V allume-cigare ou bornier sur la boîte à fusibles du van | 10 € |
| Routeur WiFi du van | **GL.iNet** (ex. Slate AX / Beryl AX) — il fait WiFi + DHCP + servira plus tard pour le VPN | 80–150 € |
| Caméras | 4× **ESP32-CAM** (module + carte programmeur FTDI, ou kit AI-Thinker) | 8–12 €/pièce |
| Capteurs (plus tard) | 3× ESP32, 2× INA226, shunt 100 A, 2× JSN-SR04T, DS18B20, MQ-7, MQ-2 | ~60 € le lot |

Branchement élec (hypothèse) : le mini PC est alimenté en permanence sur la batterie cellule
via le DC-DC 12→19 V + fusible, derrière le coupe-batterie. Conso ~10 W, négligeable.

---

## ÉTAPE 2 — Installer Ubuntu Server sur le mini PC (à la maison, avec Internet)

1. Sur un autre ordinateur (Windows/Mac), télécharger **Ubuntu Server 24.04 LTS** (fichier `.iso`)
   sur https://ubuntu.com/download/server
2. Créer une clé USB d'installation avec **Rufus** (Windows) ou **Ventoy** (plus simple :
   copier l'ISO sur la clé, c'est tout).
3. Brancher la clé USB sur le mini PC, l'allumer en tapotant **F12** (ou Fn+F12) pour choisir
   la clé USB au démarrage.
4. Dans l'installateur Ubuntu : langue Français, clavier Français, "Ubuntu Server" (pas la version
   avec bureau), **cocher "Install OpenSSH server"**, créer ton utilisateur (ex. `dokkaebi`),
   laisser le disque entier pour Ubuntu. À la fin : éjecter la clé, redémarrer.
5. Le mini PC démarre sur un écran noir avec du texte : c'est normal. Note l'adresse IP affichée
   ou fais `ip a` → ex. `192.168.1.42`.

---

## ÉTAPE 3 — Installation automatique de Dokkaebi (une seule commande)

Brancher le mini PC sur ta box Internet (câble Ethernet) à la maison. Se connecter en SSH depuis
ton ordinateur (`ssh dokkaebi@192.168.1.42`) ou directement clavier+écran sur le mini PC, puis :

```bash
# 1. télécharger le script d'installation depuis le dépôt
curl -fsSL https://raw.githubusercontent.com/<ton-compte>/dokkaebi/main/tools/install_minipc.sh -o /tmp/install.sh

# 2. le lancer (mot de passe demandé une fois)
sudo bash /tmp/install.sh https://github.com/<ton-compte>/dokkaebi.git
```

Le script fait tout tout seul : installe Docker, clone le projet dans `/opt/dokkaebi`,
précharge les images (besoin d'Internet, **une seule fois**), démarre la stack.

À la fin il affiche quelque chose comme :

```
OK ! Interface web :  http://192.168.1.42:8080
MQTT (ESP32)      :  192.168.1.42:1883
NAS (Samba)       :  smb://192.168.1.42/dokkaebi
```

Ouvre un navigateur sur ton ordinateur et va sur `http://192.168.1.42:8080` :
tu dois voir l'écran vert phospho **DOKKÆBI**. Si oui → c'est installé. 🎉

### Tester sans aucun capteur (simulateur)

```bash
cd /opt/dokkaebi
docker compose --profile sim up -d sim     # démarre le faux ESP32
docker compose logs -f sim                 # voir les mesures partir
```

Retourne sur l'interface web, onglet **ATA24 ÉLEC** : les jauges et le graphique doivent bouger
toutes les 2 secondes. Ça prouve que toute la chaîne marche.

```bash
docker compose --profile sim down          # arrêter le simulateur quand tu veux
```

---

## ÉTAPE 4 — Installation dans le van

1. Éteins le mini PC (`sudo shutdown now`), branche-le sur le 12 V du van (DC-DC + fusible).
2. Branche le mini PC en Ethernet sur le routeur GL.iNet du van. Allume le routeur, puis le mini PC.
3. **Réserver une IP fixe** au mini PC dans le routeur GL.iNet : interface admin du routeur
   (souvent `192.168.8.1`) → DHCP → "Static Lease" / réservation pour l'adresse MAC du mini PC,
   par ex. **192.168.10.1**. Comme ça, l'adresse ne change jamais.
4. Mets à jour les IP des caméras dans `/opt/dokkaebi/docker-compose.yml` (lignes `CAM1_URL`…)
   quand tu les installeras, puis `docker compose up -d` pour recharger.
5. Depuis ton téléphone/ordinateur connecté au WiFi du van (SSID du GL.iNet), ouvre
   **`http://192.168.10.1:8080`** → l'interface DOKKÆBI, 100 % locale, même en mode avion
   (il n'y a aucun accès à Internet impliqué).

---

## ÉTAPE 5 — Brancher les vraies caméras (ESP32-CAM)

1. Flasher chaque ESP32-CAM avec le firmware **CameraWebServer** (Arduino IDE → exemples
   ESP32 → Camera → CameraWebServer), en renseignant le SSID/mot de passe du WiFi du van.
2. Dans le routeur, réserver des IP fixes aux 4 caméras : 192.168.10.11 à .14.
3. Reporter ces IP dans `docker-compose.yml` (`CAM1_URL=http://192.168.10.11/stream` …),
   puis `cd /opt/dokkaebi && docker compose up -d`.
4. Onglet **CAM ×4** de l'interface : les 4 flux doivent s'afficher.

---

## ÉTAPE 6 — Brancher les capteurs (ESP32)

1. Flasher un ESP32 avec le sketch `tools/esp32_sensor.ino` (renseigner SSID/MQTT_HOST=192.168.10.1).
2. Câbler les capteurs selon le tableau du livrable 7 (INA226 sur le shunt, etc.).
3. Dès le premier démarrage, les valeurs apparaissent en direct dans les onglets ÉLEC/EAU/CLIM.

---

## ÉTAPE 7 — Accès à distance (optionnel, plus tard)

Installer **Tailscale** sur le mini PC (`curl -fsSL https://tailscale.com/install.sh | sh`,
puis `sudo tailscale up`) : le van devient joignable de ton téléphone n'importe où, via un VPN
chiffré. **Ne jamais ouvrir de port vers Internet** (pas de redirection de port sur le routeur).

---

## Commandes du quotidien (à garder sous le coude)

```bash
cd /opt/dokkaebi
docker compose ps                 # est-ce que tout tourne ?
docker compose logs -f            # voir les messages en direct
docker compose logs -f backend    # logs du backend seul
docker compose up -d              # (re)démarrer
docker compose down               # tout arrêter
docker compose pull && docker compose up -d   # mise à jour (à la maison, avec Internet)
sudo reboot                       # redémarrer le mini PC
```

## Sauvegarde

```bash
# tout est dans /opt/dokkaebi + le volume docker ; sauvegarde minimale :
sudo tar czf /root/dokkaebi-backup-$(date +%F).tgz /opt/dokkaebi
docker run --rm -v dokkaebi_dokkaebi-data:/data -v /root:/backup alpine \
  tar czf /backup/dokkaebi-data-$(date +%F).tgz /data
# copier les .tgz sur une clé USB / un autre ordi
```

## Dépannage (les 5 problèmes les plus fréquents)

| Symptôme | Cause probable | Solution |
|---|---|---|
| `http://<ip>:8080` ne répond pas | conteneur arrêté | `cd /opt/dokkaebi && docker compose ps` puis `docker compose logs -f web` / `backend` |
| Page OK mais jauges à `--` | pas de mesures | lancer le simu (`--profile sim up -d sim`) ou vérifier qu'un ESP32 publie (`docker compose logs -f mosquitto`) |
| Onglet CAM noir | mauvaise IP de caméra | vérifier `CAMx_URL` dans docker-compose.yml, ping l'IP depuis le mini PC (`ping 192.168.10.11`) |
| `docker compose up` dit "image not found" hors ligne | images pas préchargées | refaire `docker compose pull && docker compose build` à la maison avec Internet |
| Le mini PC ne démarre plus | 12 V instable | vérifier le fusible et le DC-DC ; mesurer la tension aux bornes du mini PC |

## Changer le mot de passe Samba (NAS)

Dans `docker-compose.yml`, service `nas`, remplacer `dokkaebi;dokkaebi` par
`dokkaebi;<ton-mot-de-passe>`, puis `docker compose up -d nas`.
