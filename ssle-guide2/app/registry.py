"""Service Registry: registo, descoberta, health checking e load balancing (round-robin)."""
import os
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# registry = { "ingestion-service": { "<instance_id>": {...}, ... }, ... }
registry = {}
rr_counters = {}           # contador round-robin por serviço
lock = threading.Lock()    # o Flask atende pedidos em várias threads

HEALTH_INTERVAL = 10       # segundos entre verificações
MAX_FAILURES = 3           # falhas seguidas até remover a instância


def now():
    return datetime.now(timezone.utc).isoformat()


@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name, url = data.get("name"), data.get("url")
    if not name or not url:
        return jsonify({"error": "Missing name or url"}), 400
    instance_id = data.get("instance_id") or url
    with lock:
        previous = registry.get(name, {}).get(instance_id)
        registry.setdefault(name, {})[instance_id] = {
            "instance_id": instance_id,
            "url": url,
            "location": data.get("location", {}),
            # re-registos (heartbeat) mantêm a data original de registo
            "registered_at": previous["registered_at"] if previous else now(),
            "last_seen": now(),
            "failures": 0,
        }
    if previous is None:
        print(f"[+] {instance_id} -> {url}", flush=True)
    return jsonify({"message": f"{instance_id} registered"}), 200


@app.delete("/unregister")
def unregister():
    data = request.get_json(silent=True) or {}
    name, instance_id = data.get("name"), data.get("instance_id")
    with lock:
        if name not in registry:
            return jsonify({"error": "Not found"}), 404
        if instance_id:
            if registry[name].pop(instance_id, None) is None:
                return jsonify({"error": "Not found"}), 404
        else:
            registry[name].clear()
        if not registry[name]:
            del registry[name]
    print(f"[-] {instance_id or name} unregistered")
    return jsonify({"message": "unregistered"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/services")
def services():
    with lock:
        return jsonify(registry)


@app.get("/services/<name>")
def get_service(name):
    """Discovery + load balancing: devolve UMA instância, em round-robin."""
    with lock:
        instances = list(registry.get(name, {}).values())
        if not instances:
            return jsonify({"error": "Not found"}), 404
        idx = rr_counters.get(name, 0) % len(instances)
        rr_counters[name] = idx + 1
        return jsonify(instances[idx])


def health_checker():
    while True:
        time.sleep(HEALTH_INTERVAL)
        with lock:
            snapshot = [(n, iid, inst["url"])
                        for n, insts in registry.items() for iid, inst in insts.items()]
        # Os pedidos HTTP são feitos FORA do lock para não bloquear o registry
        for name, iid, url in snapshot:
            try:
                ok = requests.get(f"{url}/health", timeout=2).status_code == 200
            except requests.RequestException:
                ok = False
            with lock:
                inst = registry.get(name, {}).get(iid)
                if inst is None:
                    continue
                if ok:
                    inst["failures"] = 0
                    inst["last_seen"] = now()
                else:
                    inst["failures"] += 1
                    print(f"[!] {iid} falhou health check ({inst['failures']}/{MAX_FAILURES})")
                    if inst["failures"] >= MAX_FAILURES:
                        del registry[name][iid]
                        if not registry[name]:
                            del registry[name]
                        print(f"[x] {iid} removido (morto)")


if __name__ == "__main__":
    threading.Thread(target=health_checker, daemon=True).start()
    app.run(host=os.getenv("BIND_HOST", "127.0.0.1"), port=int(os.getenv("PORT", 5050)))