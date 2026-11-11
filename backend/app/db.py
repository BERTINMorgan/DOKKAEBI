"""Dokkaebi — couche SQLite (schema + CRUD). Aucune dépendance externe."""
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "/data/dokkaebi.db")
PHOTOS_DIR = os.environ.get("PHOTOS_DIR", "/data/photos")

_lock = threading.RLock()
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS sensors(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  system TEXT NOT NULL,
  ata TEXT NOT NULL,
  unit TEXT DEFAULT '',
  mqtt_topic TEXT NOT NULL,
  min REAL DEFAULT 0,
  max REAL DEFAULT 100,
  alarm REAL
);
CREATE TABLE IF NOT EXISTS measures(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  sensor TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_measures ON measures(sensor, ts);
CREATE TABLE IF NOT EXISTS equipment(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ata TEXT, name TEXT, detail TEXT, hotspot TEXT
);
CREATE TABLE IF NOT EXISTS fev(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  num TEXT UNIQUE NOT NULL,
  date TEXT NOT NULL,
  ata TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  symptoms TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'ouvert',   -- ouvert | cloture | converti
  ft_link TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fev_photos(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fev_id INTEGER NOT NULL,
  original TEXT,
  filename TEXT NOT NULL,
  uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ft(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  num TEXT UNIQUE NOT NULL,                -- FT-<ATA>-<SEQ>
  ata TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'brouillon', -- brouillon | en_cours | realise | valide | archive
  fev_source_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# Capteurs connus — hypothèse de travail, extensible à chaud via table sensors.
SENSORS = [
    ("batt_voltage", "Tension batterie", "elec", "24", "V", "dokkaebi/elec/batt_voltage", 10.5, 14.8, 11.5),
    ("batt_current", "Courant batterie (+charge / -decharge)", "elec", "24", "A", "dokkaebi/elec/batt_current", -80, 120, None),
    ("batt_soc", "Etat de charge (SoC)", "elec", "24", "%", "dokkaebi/elec/batt_soc", 0, 100, 20),
    ("solar_w", "Production solaire", "elec", "24", "W", "dokkaebi/elec/solar_w", 0, 650, None),
    ("load_w", "Consommation 12V", "elec", "24", "W", "dokkaebi/elec/load_w", 0, 2200, None),
    ("temp_int", "Temperature interieure", "clim", "21", "°C", "dokkaebi/clim/temp_int", -20, 50, None),
    ("temp_ext", "Temperature exterieure", "clim", "21", "°C", "dokkaebi/clim/temp_ext", -30, 50, None),
    ("heater_state", "Chauffage diesel", "clim", "21", "0/1", "dokkaebi/clim/heater_state", 0, 1, None),
    ("co_ppm", "Detecteur CO", "secu", "26", "ppm", "dokkaebi/secu/co_ppm", 0, 1000, 30),
    ("smoke", "Detecteur fumee", "secu", "26", "0/1", "dokkaebi/secu/smoke", 0, 1, 0.5),
    ("water_fresh_l", "Niveau eau propre", "eau", "38", "L", "dokkaebi/eau/water_fresh_l", 0, 100, 10),
    ("water_grey_l", "Niveau eau grise", "eau", "38", "L", "dokkaebi/eau/water_grey_l", 0, 80, 70),
    ("boiler_temp", "Chauffe-eau calorifique", "eau", "38", "°C", "dokkaebi/eau/boiler_temp", 0, 90, None),
]

EQUIPMENT = [
    ("24", "Panneau solaire 600 Wc", "Toit, MPPT dédié", "solar"),
    ("24", "Batterie LiFePO4 2x300 Ah (7,7 kWh) + BMS", "Caisse côté conducteur (gauche)", "batt"),
    ("24", "B2B 60 A / chargeur 230 V 50 A / onduleur 2000 VA", "Coffre élec gauche", "batt"),
    ("38", "Reservoirs eau propre 100 L / grise 80 L + chauffe-eau", "Côté passager (droite)", "eau"),
    ("21", "Chauffage diesel + cheminée toit arrière", "Circuit calorifique", "heater"),
    ("26", "Detecteurs CO / fumee", "Plafond cabine", "secu"),
    ("56", "Lanterneaux et ouvrants", "Toit avant", "body"),
]

# FT d'exemple pour rendre la numérotation FT-24-07 atteignable en démo.
FT_SEED = [(f"FT-24-{i:02d}", "24", f"Fiche technique exemple {i:02d}", "brouillon") for i in range(1, 7)]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db():
    with _lock:
        c = get_conn()
        c.executescript(SCHEMA)
        for row in SENSORS:
            c.execute("INSERT OR IGNORE INTO sensors VALUES (?,?,?,?,?,?,?,?,?)", row)
        if not c.execute("SELECT 1 FROM equipment LIMIT 1").fetchone():
            for ata, name, detail, hotspot in EQUIPMENT:
                c.execute("INSERT INTO equipment(ata,name,detail,hotspot) VALUES (?,?,?,?)",
                          (ata, name, detail, hotspot))
        for num, ata, title, status in FT_SEED:
            c.execute(
                "INSERT OR IGNORE INTO ft(num,ata,title,content,status,created_at,updated_at)"
                " VALUES (?,?,?,'',?,?,?)",
                (num, ata, title, status, _now(), _now()))
        c.commit()


def q(sql, args=(), one=False):
    with _lock:
        cur = get_conn().execute(sql, args)
        rows = cur.fetchall()
        if one:
            return rows[0] if rows else None
        return rows


def rows2dicts(rows):
    return [dict(r) for r in rows]


# ---------- capteurs / mesures ----------

def list_sensors():
    return rows2dicts(q("SELECT * FROM sensors ORDER BY system, id"))


def sensor_unit(sensor_id):
    r = q("SELECT unit FROM sensors WHERE id=?", (sensor_id,), one=True)
    return r["unit"] if r else ""


def insert_measure(sensor, value, unit, ts):
    with _lock:
        get_conn().execute("INSERT INTO measures(ts,sensor,value,unit) VALUES (?,?,?,?)",
                           (ts, sensor, value, unit))
        get_conn().commit()


def measures(sensor=None, frm=None, to=None, limit=500):
    sql = "SELECT ts,sensor,value,unit FROM measures WHERE 1=1"
    args = []
    if sensor:
        sql += " AND sensor=?"
        args.append(sensor)
    if frm is not None:
        sql += " AND ts>=?"
        args.append(frm)
    if to is not None:
        sql += " AND ts<=?"
        args.append(to)
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(int(limit))
    rows = rows2dicts(q(sql, args))
    rows.reverse()
    return rows


def latest():
    rows = q("""SELECT m.sensor, m.value, m.unit, m.ts FROM measures m
                JOIN (SELECT sensor, MAX(ts) ts FROM measures GROUP BY sensor) l
                  ON l.sensor=m.sensor AND l.ts=m.ts""")
    return {r["sensor"]: dict(r) for r in rows}


def list_equipment():
    return rows2dicts(q("SELECT * FROM equipment ORDER BY ata"))


# ---------- FEV ----------

def next_fev_num():
    mx = 0
    for r in q("SELECT num FROM fev"):
        m = re.match(r"FEV-(\d+)$", r["num"] or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return f"FEV-{mx + 1:03d}"


def list_fev(status=None):
    if status:
        return rows2dicts(q("SELECT * FROM fev WHERE status=? ORDER BY id DESC", (status,)))
    return rows2dicts(q("SELECT * FROM fev ORDER BY id DESC"))


def get_fev(fev_id):
    fev = q("SELECT * FROM fev WHERE id=?", (fev_id,), one=True)
    if not fev:
        return None
    d = dict(fev)
    d["photos"] = rows2dicts(q("SELECT * FROM fev_photos WHERE fev_id=?", (fev_id,)))
    return d


def create_fev(date, ata, title, description="", symptoms=""):
    num = next_fev_num()
    now = _now()
    with _lock:
        get_conn().execute(
            "INSERT INTO fev(num,date,ata,title,description,symptoms,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,'ouvert',?,?)",
            (num, date, ata, title, description, symptoms, now, now))
        get_conn().commit()
    return get_fev(q("SELECT id FROM fev WHERE num=?", (num,), one=True)["id"])


def update_fev(fev_id, **fields):
    allowed = {"date", "ata", "title", "description", "symptoms", "status", "ft_link"}
    sets = [f"{k}=?" for k in fields if k in allowed]
    if not sets:
        return get_fev(fev_id)
    sets.append("updated_at=?")
    args = [fields[k] for k in fields if k in allowed] + [_now(), fev_id]
    with _lock:
        get_conn().execute(f"UPDATE fev SET {','.join(sets)} WHERE id=?", args)
        get_conn().commit()
    return get_fev(fev_id)


def close_fev(fev_id):
    return update_fev(fev_id, status="cloture")


def add_photo(fev_id, original, filename):
    with _lock:
        get_conn().execute(
            "INSERT INTO fev_photos(fev_id,original,filename,uploaded_at) VALUES (?,?,?,?)",
            (fev_id, original, filename, _now()))
        get_conn().commit()


# ---------- FT ----------

def next_ft_num(ata):
    mx = 0
    for r in q("SELECT num FROM ft WHERE num LIKE ?", (f"FT-{ata}-%",)):
        m = re.match(r"FT-\d+-(\d+)$", r["num"] or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return f"FT-{ata}-{mx + 1:02d}"


def list_ft():
    return rows2dicts(q("SELECT * FROM ft ORDER BY ata, num"))


def get_ft(num):
    r = q("SELECT * FROM ft WHERE num=?", (num,), one=True)
    return dict(r) if r else None


def create_ft(num, ata, title, content="", fev_source_id=None, status="brouillon"):
    now = _now()
    with _lock:
        get_conn().execute(
            "INSERT INTO ft(num,ata,title,content,status,fev_source_id,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (num, ata, title, content, status, fev_source_id, now, now))
        get_conn().commit()
    return get_ft(num)


def update_ft(num, **fields):
    allowed = {"title", "content", "status", "ata"}
    sets = [f"{k}=?" for k in fields if k in allowed]
    if not sets:
        return get_ft(num)
    sets.append("updated_at=?")
    args = [fields[k] for k in fields if k in allowed] + [_now(), num]
    with _lock:
        get_conn().execute(f"UPDATE ft SET {','.join(sets)} WHERE num=?", args)
        get_conn().commit()
    return get_ft(num)


def convert_fev_to_ft(fev_id, ata=None, content=None):
    """Règle de conversion FEV -> FT : numérotation FT-<ATA>-<SEQ+1> du chapitre,
    FEV passée à 'converti' avec ft_link renseigné, historique conservé (fev_source_id)."""
    fev = get_fev(fev_id)
    if not fev:
        return None, "FEV introuvable"
    if fev["status"] == "converti":
        return None, f"déjà convertie ({fev['ft_link']})"
    ata = (ata or fev["ata"] or "99").strip()
    num = next_ft_num(ata)
    body = content if content is not None else (
        f"Source : {fev['num']} ({fev['date']})\n\n{fev['description']}\n\n"
        f"Symptômes : {fev['symptoms']}")
    create_ft(num=num, ata=ata, title=fev["title"], content=body, fev_source_id=fev_id,
              status="brouillon")
    update_fev(fev_id, status="converti", ft_link=num, ata=ata)
    return num, None
