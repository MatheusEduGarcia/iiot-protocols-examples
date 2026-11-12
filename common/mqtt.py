"""Tiny helpers shared by the MQTT examples."""
import os

import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))


def client(client_id: str = "", **kwargs) -> mqtt.Client:
    """paho-mqtt 2.x client with the v2 callback API."""
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, **kwargs)
