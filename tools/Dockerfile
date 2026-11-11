FROM python:3.12-slim
RUN pip install --no-cache-dir paho-mqtt
COPY esp32_simulator.py /sim/esp32_simulator.py
ENV MQTT_HOST=mosquitto
CMD ["python", "-u", "/sim/esp32_simulator.py"]
