// ESP32 capteur Dokkaebi — publie la télémétrie en MQTT (JSON) sur le WiFi du van.
// Librairies Arduino : PubSubClient (Nick O'Leary). Broker : mosquitto du mini PC.
// Adapte WIFI_SSID/WIFI_PASS/MQTT_HOST et les broches capteurs à ton montage.
#include <WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID = "DOKKAEBI-VAN";
const char* WIFI_PASS = "********";
const char* MQTT_HOST = "192.168.10.1";   // mini PC
const char* MQTT_USER = nullptr;           // broker en allow_anonymous (LAN isolé)
const char* MQTT_PASS = nullptr;
const char* CLIENT_ID = "esp32-capteurs-01";

WiFiClient net;
PubSubClient mqtt(net);

// Broches (exemples) : INA226 en I2C pour V/I batterie, DS18B20, capteur niveau, etc.
void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print('.'); }
  Serial.println("WiFi OK " + WiFi.localIP().toString());

  mqtt.setServer(MQTT_HOST, 1883);
  while (!mqtt.connected()) {
    if (mqtt.connect(CLIENT_ID, /*willTopic*/ "dokkaebi/esp32/esp32-capteurs-01/status",
                     /*willQoS*/ 1, /*retain*/ true, "offline")) {
      mqtt.publish("dokkaebi/esp32/esp32-capteurs-01/status", "online", true);
      mqtt.subscribe("dokkaebi/esp32/esp32-capteurs-01/cmd/#");
    } else {
      delay(2000);
    }
  }
}

// Publie une mesure : topic dokkaebi/<systeme>/<capteur>, payload {"value":..,"unit":".."}
void publishMeasure(const char* system, const char* sensor, float value, const char* unit) {
  char topic[96], payload[64];
  snprintf(topic, sizeof topic, "dokkaebi/%s/%s", system, sensor);
  snprintf(payload, sizeof payload, "{\"value\":%.3f,\"unit\":\"%s\"}", value, unit);
  mqtt.publish(topic, payload, /*retain=*/false);  // QoS 0 suffisant en local ; QoS 1 si critique
  Serial.printf("%s -> %s\n", topic, payload);
}

void loop() {
  if (!mqtt.connected()) setup();
  mqtt.loop();

  // --- exemples de mesures (remplacer par les vraies lectures capteurs) ---
  publishMeasure("elec", "batt_voltage", 12.83, "V");     // INA226 / diviseur + ADC
  publishMeasure("elec", "batt_current", -12.40, "A");     // INA226 sur shunt 100A/75mV
  publishMeasure("elec", "batt_soc",     78.5,  "%");      // BMS (JBD/Bluetooth série) ou coulométrie
  publishMeasure("elec", "solar_w",      412.0, "W");      // Victron SmartSolar ou INA226 branche PV
  publishMeasure("clim", "temp_int",     21.4,  "°C");     // DS18B20 / SHT31
  publishMeasure("secu", "co_ppm",       3,     "ppm");    // MQ-7 (chauffage) — moyenné 60 s
  publishMeasure("secu", "smoke",        0,     "0/1");    // MQ-2
  publishMeasure("eau",  "water_fresh_l", 64.0, "L");      // capteur ultrason JSN-SR04T ou jauge résistive
  publishMeasure("eau",  "water_grey_l",  12.0, "L");
  publishMeasure("eau",  "boiler_temp",  45.0, "°C");
  publishMeasure("clim", "heater_state", 1,     "0/1");    // état relais chauffage diesel

  delay(5000);  // période d'échantillonnage
}
