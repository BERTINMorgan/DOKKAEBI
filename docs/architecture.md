# Architecture DOKKÆBI van-os (100 % locale)

```
┌────────────── WiFi du van (LAN isolé, 192.168.10.0/24) ──────────────┐
│                                                                        │
│  ESP32 capteurs ×3 ──MQTT/JSON──▶ ┌───────────┐    ┌──────────────┐  │
│  (INA226, DS18B20, MQ-7/2,         │Mosquitto  │───▶│ backend      │  │
│   niveaux eau, relais...)          │ :1883     │    │ FastAPI      │  │
│     topic dokkaebi/<sys>/<cap>     └───────────┘    │  ├─ SQLite   │  │
│     payload {"value":..,"unit":..}        ▲        │  │ /data/     │  │
│                                            │        │  └─▶ WS /ws ─┼──┼──▶ nginx :8080 ─▶ navigateur UI rétro
│  ESP32-CAM ×4 ──HTTP MJPEG :81/stream─────┼───────▶│  proxy /cam/N ─┼──┘   (aucune ressource externe)
│  (firmware CameraWebServer stock)         │        └──────────────┘  │
│                                            │                          │
│  mini PC ──VPN (WireGuard/Tailscale)──────┘  accès distant OPTIONNEL, │
│  jamais d'exposition publique                                         │
│                                                                        │
│  NAS : partage Samba (dperson/samba) sur le volume /data               │
│        smb://<mini-pc>/dokkaebi  →  /data/{dokkaebi.db, photos/, box/} │
└────────────────────────────────────────────────────────────────────────┘
```

Flux de données :
1. ESP32 publie `dokkaebi/elec/batt_voltage {"value":12.83,"unit":"V"}` (QoS 1, LWT `.../status`).
2. Mosquitto (local) → backend paho abonné `dokkaebi/#` → `INSERT INTO measures` + broadcast WS.
3. Navigateur (WS /ws via nginx) → jauge + courbe F(t) mises à jour en direct.
4. Caméras : le navigateur demande `/cam/1`, nginx proxy → backend qui stream
   `http://192.168.10.11/stream` (MJPEG) en `multipart/x-mixed-replace`.
5. FEV/FT : CRUD REST sur SQLite ; conversion FEV→FT calcule `FT-<ATA>-<SEQ+1>`.
