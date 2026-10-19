"""Sensor de temperatura (simulado): produtor de dados que inicia o pipeline."""
import os
import random
import time

import requests

from common import LOCATION, discover

DEVICE_ID = os.getenv("DEVICE_ID", f"{LOCATION['country']}.{LOCATION['region']}"
                                   f".{LOCATION['datacenter']}.sensor-001")
INTERVAL = float(os.getenv("INTERVAL", 5))


def send_temp():
    while True:
        payload = {"device_id": DEVICE_ID, "temperature": round(random.uniform(20.0, 30.0), 2)}
        ingestion_url = discover("ingestion-service")   # descoberta a cada envio
        if not ingestion_url:
            print("ingestion-service não encontrado no registry")
        else:
            try:
                r = requests.post(f"{ingestion_url}/ingest", json=payload, timeout=3)
                print("Sent:", payload, "->", r.status_code, r.json(), flush=True)
            except requests.RequestException as e:
                print("Error:", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    send_temp()