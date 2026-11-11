"""Dokkaebi van-os — backend FastAPI : REST FEV/FT + mesures, WebSocket live, proxy caméras."""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import (FastAPI, File, HTTPException, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .mqtt_ingest import start_mqtt

FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "web", "static"))

# Hypothèse : 4 ESP32-CAM en IP fixe sur le WiFi du van (à ajuster selon ton plan d'adressage).
CAMS = {
    1: os.environ.get("CAM1_URL", "http://192.168.10.11/stream"),
    2: os.environ.get("CAM2_URL", "http://192.168.10.12/stream"),
    3: os.environ.get("CAM3_URL", "http://192.168.10.13/stream"),
    4: os.environ.get("CAM4_URL", "http://192.168.10.14/stream"),
}
CAM_NAMES = {1: "CAM1 AVANT", 2: "CAM2 ARRIÈRE", 3: "CAM3 LATÉRAL GAUCHE", 4: "CAM4 LATÉRAL DROIT"}

# ---------------- hub WebSocket ----------------
_clients = set()
_loop = None


async def _broadcast(msg: dict):
    dead = []
    for ws in list(_clients):
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


def publish_measure(sensor, value, unit, ts=None):
    ts = ts if ts is not None else time.time()
    db.insert_measure(sensor, value, unit, ts)
    if _loop is not None:
        asyncio.run_coroutine_threadsafe(
            _broadcast({"type": "measure", "sensor": sensor, "value": value,
                        "unit": unit, "ts": ts}), _loop)


def on_mqtt(topic, payload):
    """Trame MQTT : topic dokkaebi/<systeme>/<capteur>, payload JSON
    {"value": 12.8, "unit": "V"} ou nombre brut."""
    sensor = topic.rstrip("/").split("/")[-1]
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            value = float(data["value"])
            unit = data.get("unit") or db.sensor_unit(sensor)
        else:
            value = float(data)
            unit = db.sensor_unit(sensor)
    except Exception as e:
        print(f"[ingest] trame invalide sur {topic}: {payload!r} ({e})")
        return
    publish_measure(sensor, value, unit)


@asynccontextmanager
async def lifespan(app):
    global _loop
    _loop = asyncio.get_running_loop()
    db.init_db()
    start_mqtt(on_mqtt)
    yield


app = FastAPI(title="Dokkaebi van-os", lifespan=lifespan)


# ---------------- WebSocket ----------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive
    except WebSocketDisconnect:
        _clients.discard(ws)
    except Exception:
        _clients.discard(ws)


# ---------------- télémétrie ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time()}


@app.get("/api/sensors")
def api_sensors():
    return db.list_sensors()


@app.get("/api/equipment")
def api_equipment():
    return db.list_equipment()


@app.get("/api/measures")
def api_measures(sensor: str | None = None, frm: float | None = None,
                 to: float | None = None, limit: int = 500):
    return db.measures(sensor=sensor, frm=frm, to=to, limit=min(limit, 5000))


@app.get("/api/latest")
def api_latest():
    return db.latest()


@app.post("/api/ingest")
async def api_ingest(req: Request):
    """Ingestion HTTP de secours (simulateur / debug sans broker) :
    POST {"topic": "dokkaebi/elec/batt_voltage", "payload": {"value": 12.8, "unit": "V"}}"""
    data = await req.json()
    topic = data.get("topic", "dokkaebi/sim/unknown")
    payload = data.get("payload", data.get("value"))
    on_mqtt(topic, json.dumps(payload))
    return {"ok": True}


# ---------------- FEV ----------------
@app.get("/api/fev")
def api_fev_list(status: str | None = None):
    return db.list_fev(status)


@app.post("/api/fev")
async def api_fev_create(req: Request):
    b = await req.json()
    for k in ("date", "ata", "title"):
        if not b.get(k):
            raise HTTPException(422, f"champ requis: {k}")
    return db.create_fev(b["date"], b["ata"], b["title"],
                         b.get("description", ""), b.get("symptoms", ""))


@app.get("/api/fev/{fev_id}")
def api_fev_get(fev_id: int):
    fev = db.get_fev(fev_id)
    if not fev:
        raise HTTPException(404, "FEV introuvable")
    return fev


@app.patch("/api/fev/{fev_id}")
async def api_fev_patch(fev_id: int, req: Request):
    if not db.get_fev(fev_id):
        raise HTTPException(404, "FEV introuvable")
    return db.update_fev(fev_id, **(await req.json()))


@app.post("/api/fev/{fev_id}/close")
def api_fev_close(fev_id: int):
    if not db.get_fev(fev_id):
        raise HTTPException(404, "FEV introuvable")
    return db.close_fev(fev_id)


@app.post("/api/fev/{fev_id}/convert")
async def api_fev_convert(fev_id: int, req: Request):
    body = await req.json() if (await req.body()) else {}
    num, err = db.convert_fev_to_ft(fev_id, body.get("ata"), body.get("content"))
    if err == "FEV introuvable":
        raise HTTPException(404, err)
    if err:
        raise HTTPException(409, err)
    return {"ft": num, "fev": db.get_fev(fev_id)}


@app.post("/api/fev/{fev_id}/photos")
async def api_fev_photos(fev_id: int, files: list[UploadFile] = File(...)):
    if not db.get_fev(fev_id):
        raise HTTPException(404, "FEV introuvable")
    os.makedirs(db.PHOTOS_DIR, exist_ok=True)
    saved = []
    for f in files:
        name = f"fev{fev_id}_{int(time.time() * 1000)}_{os.path.basename(f.filename)}"
        with open(os.path.join(db.PHOTOS_DIR, name), "wb") as fh:
            fh.write(await f.read())
        db.add_photo(fev_id, f.filename, name)
        saved.append(name)
    return {"photos": saved}


@app.get("/api/photos/{name}")
def api_photo(name: str):
    path = os.path.join(db.PHOTOS_DIR, os.path.basename(name))
    if not os.path.isfile(path):
        raise HTTPException(404, "photo introuvable")
    return FileResponse(path)


# ---------------- FT ----------------
@app.get("/api/ft")
def api_ft_list():
    return db.list_ft()


@app.post("/api/ft")
async def api_ft_create(req: Request):
    b = await req.json()
    ata = (b.get("ata") or "").strip()
    if not ata or not b.get("title"):
        raise HTTPException(422, "champs requis: ata, title")
    num = b.get("num") or db.next_ft_num(ata)
    if db.get_ft(num):
        raise HTTPException(409, f"{num} existe déjà")
    return db.create_ft(num=num, ata=ata, title=b["title"],
                        content=b.get("content", ""),
                        fev_source_id=b.get("fev_source_id"),
                        status=b.get("status", "brouillon"))


@app.get("/api/ft/{num}")
def api_ft_get(num: str):
    ft = db.get_ft(num)
    if not ft:
        raise HTTPException(404, "FT introuvable")
    return ft


@app.patch("/api/ft/{num}")
async def api_ft_patch(num: str, req: Request):
    if not db.get_ft(num):
        raise HTTPException(404, "FT introuvable")
    return db.update_ft(num, **(await req.json()))


# ---------------- caméras (proxy MJPEG ESP32-CAM) ----------------
@app.get("/api/cameras")
def api_cameras():
    return [{"id": i, "name": CAM_NAMES[i], "src": f"/cam/{i}"} for i in sorted(CAMS)]


@app.get("/cam/{n}")
async def cam_proxy(n: int):
    url = CAMS.get(n)
    if not url:
        raise HTTPException(404, "caméra inconnue")
    client = httpx.AsyncClient(timeout=None)
    ctx = client.stream("GET", url)
    try:
        resp = await ctx.__aenter__()
    except Exception as e:
        await client.aclose()
        raise HTTPException(502, f"caméra {n} injoignable ({url}): {e}")
    if resp.status_code != 200:
        await ctx.__aexit__(None, None, None)
        await client.aclose()
        raise HTTPException(502, f"caméra {n} répond HTTP {resp.status_code}")

    async def gen():
        try:
            async for chunk in resp.aiter_raw(4096):
                yield chunk
        finally:
            await ctx.__aexit__(None, None, None)
            await client.aclose()

    return StreamingResponse(
        gen(),
        media_type=resp.headers.get("content-type",
                                    "multipart/x-mixed-replace; boundary=frame"))


# ---------------- frontend statique (utile hors docker-compose aussi) ----------------
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
