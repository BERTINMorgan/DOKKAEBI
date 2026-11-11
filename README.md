# DOKKÆBI van-os — supervision/maintenance embarquée 100 % locale

Interface web locale hébergée sur le mini PC du fourgon (qui fait aussi NAS).
Fonctionne sans Internet (réseau local du van uniquement, mode avion OK).

## Démarrage rapide (sur le mini PC)

```bash
# UNE fois, à l'atelier avec Internet (préchargement des images) :
docker compose pull && docker compose build

# Dans le van, hors ligne :
docker compose up -d
# UI : http://<ip-du-mini-pc>:8080   (ex. http://192.168.10.1:8080)
# MQTT : <ip-du-mini-pc>:1883        (ESP32 capteurs)
# NAS  : smb://<ip-du-mini-pc>/dokkaebi  (user dokkaebi / pass dokkaebi — À CHANGER)
```

Test sans matériel : `python3 tools/esp32_simulator.py` publie la télémétrie
(MQTT si le broker tourne, sinon HTTP vers `POST /api/ingest`).

## Arborescence

```
dokkaebi/
├── docker-compose.yml        # mosquitto + backend + web + nas
├── mosquitto/mosquitto.conf  # broker local, LAN only
├── backend/                  # FastAPI : REST FEV/FT + mesures, WS /ws, proxy /cam/N, SQLite
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/{main.py,db.py,mqtt_ingest.py}
├── web/                      # nginx + statique rétro-pixel (aucune ressource externe)
│   ├── Dockerfile  nginx.conf
│   └── static/{index.html, css/retro.css, js/{app.js, miniplot.js}}
├── nas/                      # (config Samba via dperson/samba dans compose)
├── tools/esp32_simulator.py  # simulateur de télémétrie
├── tools/esp32_sensor.ino    # sketch ESP32 capteurs (PubSubClient)
└── docs/                     # schémas, plan capteurs
```

## Stockage (volume `dokkaebi-data` monté sur /data, partagé avec le NAS)

```
/data/
├── dokkaebi.db               # SQLite (WAL) : mesures, sensors, fev, ft, photos
├── photos/                   # uploads photos FEV (servis via /api/photos/<fichier>)
└── box/                      # arborescence fiches par chapitre ATA (FT-24-01.md, ...)
    ├── ATA-21/  ATA-24/  ATA-25/  ATA-26/  ATA-31/
    ├── ATA-33/  ATA-38/  ATA-51/  ATA-53/  ATA-56/
```

## API (prefixe /api, proxyfiée par nginx)

| Méthode | Route | Rôle |
|---|---|---|
| GET | /api/sensors | capteurs connus |
| GET | /api/measures?sensor=&frm=&to=&limit= | historique mesures |
| GET | /api/latest | dernières valeurs |
| POST | /api/ingest | ingestion HTTP de secours `{"topic","payload"}` |
| WS | /ws | push live `{"type":"measure",...}` |
| GET/POST | /api/fev · GET/PATCH /api/fev/{id} | CRUD FEV |
| POST | /api/fev/{id}/close | clôture |
| POST | /api/fev/{id}/convert | FEV → FT-<ATA>-<SEQ+1> |
| POST | /api/fev/{id}/photos | upload photos (multipart) |
| GET | /api/photos/{name} | photo |
| GET/POST | /api/ft · GET/PATCH /api/ft/{num} | CRUD FT + workflow |
| GET | /api/cameras · GET /cam/{1..4} | liste + proxy MJPEG ESP32-CAM |

## Sécurité

- Aucune exposition Internet : ports publiés uniquement sur le LAN du van ;
  accès distant via VPN (WireGuard/Tailscale) sur le mini PC uniquement.
- Broker MQTT en `allow_anonymous` sur LAN isolé (hypothèse) — durcir avec
  `password_file` si le WiFi du van peut accueillir des invités.
- À faire en v2 : authentification légère sur l'UI (session locale) avant toute
  écriture FEV/FT depuis un poste invité.

## Hors-ligne strict

Aucune ressource externe : polices = stack mono système, graphiques = canvas
custom (`miniplot.js`), 3D = SVG isométrique inline, zéro CDN/font/APi cloud.
Précharger les images Docker une fois (`docker compose pull && build`), ensuite
`docker compose up -d` fonctionne sans aucune connexion.
