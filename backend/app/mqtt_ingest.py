"""Ingestion MQTT : subscribe dokkaebi/# sur le broker local, callback vers le hub."""
import os

TOPIC_PREFIX = "dokkaebi/"


def start_mqtt(on_message):
    """Démarre le client paho en thread. Si le broker est injoignable, on dégrade
    gracieusement : l'ingestion reste possible via POST /api/ingest (HTTP)."""
    if os.environ.get("MQTT_ENABLED", "1") == "0":
        print("[mqtt] désactivé (MQTT_ENABLED=0)")
        return None
    host = os.environ.get("MQTT_HOST", "mosquitto")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[mqtt] paho-mqtt absent — ingestion HTTP seule")
        return None

    def _on(client, userdata, msg):
        try:
            on_message(msg.topic, msg.payload.decode("utf-8", "replace"))
        except Exception as e:
            print(f"[mqtt] message ignoré ({msg.topic}): {e}")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:  # paho-mqtt < 2.0
        client = mqtt.Client()
    client.on_message = _on
    client.reconnect_delay_set(1, 10)
    try:
        client.connect(host, port, 60)
        client.subscribe(f"{TOPIC_PREFIX}#")
        client.loop_start()
        print(f"[mqtt] connecté à {host}:{port}, abonné à {TOPIC_PREFIX}#")
        return client
    except Exception as e:
        print(f"[mqtt] broker {host}:{port} injoignable ({e}) — repli HTTP /api/ingest")
        return None
