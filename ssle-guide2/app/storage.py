"""Storage Service: único componente que fala com a base de dados."""
import os
import sqlite3

from flask import Flask, jsonify, request

from common import BIND_HOST, service_url, make_instance_id, register_service

SERVICE_NAME = "storage-service"
PORT = int(os.getenv("PORT", 5002))
DB = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_data.db"))

INSTANCE_ID = make_instance_id(SERVICE_NAME, PORT)

app = Flask(__name__)


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS temperatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                temperature REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/store")
def store():
    data = request.get_json(silent=True) or {}
    if "device_id" not in data or "temperature" not in data:
        return jsonify({"error": "device_id and temperature required"}), 400
    with sqlite3.connect(DB) as conn:
        # Query parametrizada (?) -> protege contra SQL injection
        conn.execute("INSERT INTO temperatures (device_id, temperature) VALUES (?, ?)",
                     (data["device_id"], data["temperature"]))
    return jsonify({"status": "stored"}), 200


@app.get("/temperatures")
def list_temperatures():
    """API de leitura: o Analytics usa isto em vez de abrir a BD diretamente."""
    limit = min(request.args.get("limit", 100, type=int), 1000)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT device_id, temperature, timestamp FROM temperatures "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    register_service(SERVICE_NAME, service_url(PORT), INSTANCE_ID)
    app.run(host=BIND_HOST, port=PORT)