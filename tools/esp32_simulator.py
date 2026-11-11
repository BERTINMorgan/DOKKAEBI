#!/usr/bin/env python3
"""Simulateur ESP32 — publie la télémétrie Dokkaebi toutes les 2 s.
Mode MQTT si le broker est joignable, sinon repli HTTP sur POST /api/ingest.
Usage : python3 tools/esp32_simulator.py   (MQTT_HOST=127.0.0.1 API=http://127.0.0.1:8000/api/ingest)
"""
import json
import math
import os
import time
import urllib.request

MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
API = os.environ.get("API", "http://127.0.0.1:8000/api/ingest")


def payloads(t):
    solar = max(0.0, 540 * math.sin(t / 45) ** 2) if 6 <= (t / 3600) % 24 < 19 else 0.0
    return {
        "dokkaebi/elec/batt_voltage": {"value": round(12.4 + 0.9 * math.sin(t / 40) + 0.05 * math.sin(t / 3), 3), "unit": "V"},
        "dokkaebi/elec/batt_current": {"value": round(-14 + 18 * math.sin(t / 25) + solar / 14, 2), "unit": "A"},
        "dokkaebi/elec/batt_soc": {"value": round(max(0, min(100, 62 + 30 * math.sin(t / 150))), 1), "unit": "%"},
        "dokkaebi/elec/solar_w": {"value": round(solar, 1), "unit": "W"},
        "dokkaebi/elec/load_w": {"value": round(180 + 90 * math.sin(t / 11), 1), "unit": "W"},
        "dokkaebi/clim/temp_int": {"value": round(19.5 + 2.5 * math.sin(t / 90), 1), "unit": "°C"},
        "dokkaebi/clim/temp_ext": {"value": round(8 + 6 * math.sin(t / 150), 1), "unit": "°C"},
        "dokkaebi/clim/heater_state": {"value": 1 if math.sin(t / 200) > 0.2 else 0, "unit": "0/1"},
        "dokkaebi/secu/co_ppm": {"value": 2, "unit": "ppm"},
        "dokkaebi/secu/smoke": {"value": 0, "unit": "0/1"},
        "dokkaebi/eau/water_fresh_l": {"value": round(64 - (t / 300) % 40, 1), "unit": "L"},
        "dokkaebi/eau/water_grey_l": {"value": round((t / 300) % 35, 1), "unit": "L"},
        "dokkaebi/eau/boiler_temp": {"value": round(38 + 12 * math.sin(t / 80), 1), "unit": "°C"},
    }


def main():
    client = None
    try:
        import paho.mqtt.client as mqtt
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            client = mqtt.Client()
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()  # indispensable : boucle réseau paho (sinon rien n'est envoyé)
        mode = f"mqtt://{MQTT_HOST}:{MQTT_PORT}"
    except Exception as e:
        mode = f"http {API} (broker injoignable: {e})"
    print(f"[sim] dokkaebi telemetry — mode {mode}")
    t0 = time.time()
    while True:
        t = time.time() - t0
        for topic, p in payloads(t).items():
            if client:
                client.publish(topic, json.dumps(p), qos=1)
            else:
                req = urllib.request.Request(
                    API, data=json.dumps({"topic": topic, "payload": p}).encode(),
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=5).read()
        time.sleep(2)


if __name__ == "__main__":
    main()
