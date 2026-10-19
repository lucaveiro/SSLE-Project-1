"""Analytics Service: transforma dados em informação (média, min, max, anomalias)."""
import os

import requests
from flask import Flask, jsonify, request

from common import BIND_HOST, service_url, discover, make_instance_id, register_service

SERVICE_NAME = "analytics-service"
PORT = int(os.getenv("PORT", 5003))
ANOMALY_THRESHOLD = 28.0

INSTANCE_ID = make_instance_id(SERVICE_NAME, PORT)

app = Flask(__name__)


def fetch_readings(limit):
    storage_url = discover("storage-service")
    if not storage_url:
        return None
    try:
        r = requests.get(f"{storage_url}/temperatures", params={"limit": limit}, timeout=3)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/average")
def average_temp():
    readings = fetch_readings(request.args.get("limit", 100, type=int))
    if readings is None:
        return jsonify({"error": "storage-service unavailable"}), 503
    temps = [r["temperature"] for r in readings]
    if not temps:
        return jsonify({"average_temperature": None, "count": 0})
    return jsonify({
        "average_temperature": round(sum(temps) / len(temps), 2),
        "min": min(temps),
        "max": max(temps),
        "count": len(temps),
    })


@app.get("/anomalies")
def anomalies():
    readings = fetch_readings(request.args.get("limit", 100, type=int))
    if readings is None:
        return jsonify({"error": "storage-service unavailable"}), 503
    return jsonify([r for r in readings if r["temperature"] > ANOMALY_THRESHOLD])


if __name__ == "__main__":
    register_service(SERVICE_NAME, service_url(PORT), INSTANCE_ID)
    app.run(host=BIND_HOST, port=PORT)