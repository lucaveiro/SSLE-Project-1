import json, sys

try:
    d = json.load(sys.stdin)
    mx = d.get("max")
    avg = d.get("average_temperature")
    if mx is not None:
        if mx > 150 or mx < -50:
            print(f"[ANOMALY] temperature out of physical range: max={mx} avg={avg}", flush=True)
        else:
            print(f"[CHECK] max={mx} avg={avg}", flush=True)
except Exception as e:
    print(f"[ERROR] {e}", flush=True)
