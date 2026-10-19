"""Ingestion Service: recebe dados, valida/normaliza e encaminha para o Storage."""
import os

import requests
from flask import Flask, jsonify, request

from common import BIND_HOST, service_url, discover, make_instance_id, register_service

SERVICE_NAME = "ingestion-service"
PORT = int(os.getenv("PORT", 5001))

INSTANCE_ID = make_instance_id(SERVICE_NAME, PORT)

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/ingest")
def ingest():
    data = request.get_json(silent=True)
    # 1) Validação
    if not isinstance(data, dict) or "device_id" not in data or "temperature" not in data:
        return jsonify({"error": "device_id and temperature required"}), 400
    try:
        temp = float(data["temperature"])
    except (TypeError, ValueError):
        return jsonify({"error": "temperature must be numeric"}), 400
    if not -50.0 <= temp <= 150.0:
        return jsonify({"error": "temperature out of range"}), 422

    # 2) Normalização
    record = {"device_id": str(data["device_id"])[:64], "temperature": round(temp, 2)}
    print(f"[{INSTANCE_ID}] Received:", record, flush=True)

    # 3) Routing: descobrir o storage via registry (nada hardcoded)
    storage_url = discover("storage-service")
    if not storage_url:
        return jsonify({"error": "storage-service unavailable"}), 503
    try:
        res = requests.post(f"{storage_url}/store", json=record, timeout=3)
        return jsonify({"stored": res.ok, "handled_by": INSTANCE_ID}), res.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    register_service(SERVICE_NAME, service_url(PORT), INSTANCE_ID)
    app.run(host=BIND_HOST, port=PORT)