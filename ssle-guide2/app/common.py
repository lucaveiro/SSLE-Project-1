"""
Funções partilhadas por todos os serviços:
  - construção do ID hierárquico da instância
  - registo/desregisto no Service Registry
  - descoberta de outros serviços
"""
import atexit
import os
import signal
import sys
import threading
import time

import requests

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://127.0.0.1:5050")
# Interface onde o Flask escuta: 127.0.0.1 em desenvolvimento; os containers definem 0.0.0.0
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
# Intervalo de re-registo (o registry guarda tudo em memória: se reiniciar, os serviços voltam a aparecer)
HEARTBEAT = int(os.getenv("HEARTBEAT", 15))

# Localização física/lógica da instância (país > região > datacenter > rack > nó).
LOCATION = {
    "country": os.getenv("LOC_COUNTRY", "pt"),
    "region": os.getenv("LOC_REGION", "centro"),
    "datacenter": os.getenv("LOC_DC", "dc-aveiro"),
    "rack": os.getenv("LOC_RACK", "rack01"),
    "node": os.getenv("LOC_NODE", "node01"),
}


def make_instance_id(service_name: str, port: int) -> str:
    """Ex.: pt.centro.dc-aveiro.rack01.node01.ingestion-service.5001

    O último segmento é a porta por omissão. Em Kubernetes, várias réplicas no mesmo nó
    usam a mesma porta, por isso a variável INSTANCE (nome do pod) substitui-a.
    """
    loc = LOCATION
    return ".".join([loc["country"], loc["region"], loc["datacenter"],
                     loc["rack"], loc["node"], service_name,
                     os.getenv("INSTANCE", str(port))])


def service_url(port: int) -> str:
    """URL pelo qual os OUTROS serviços chegam a esta instância (não pode ser 127.0.0.1 em containers)."""
    return os.getenv("SERVICE_URL", f"http://127.0.0.1:{port}")


def register_service(name: str, url: str, instance_id: str) -> None:
    """Regista em background, com retries (o registry pode ainda não estar ativo)."""
    payload = {"name": name, "url": url, "instance_id": instance_id, "location": LOCATION}

    def _worker():
        registered = False
        while True:
            try:
                ok = requests.post(f"{REGISTRY_URL}/register", json=payload, timeout=2).ok
            except requests.RequestException:
                ok = False
            if ok and not registered:
                print(f"[registry] registado como {instance_id} ({url})", flush=True)
            elif not ok:
                print("[registry] indisponível, nova tentativa em 3s...", flush=True)
            registered = ok
            # Heartbeat: continua a re-registar mesmo depois de sucesso
            time.sleep(HEARTBEAT if ok else 3)

    threading.Thread(target=_worker, daemon=True).start()

    # Ao terminar (Ctrl+C), sair do diretório de forma limpa
    def _unregister():
        try:
            requests.delete(f"{REGISTRY_URL}/unregister",
                            json={"name": name, "instance_id": instance_id}, timeout=2)
        except requests.RequestException:
            pass
    atexit.register(_unregister)
    # SIGTERM (docker stop, kill, OpenShift) -> saída normal -> atexit corre
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


def discover(name: str):
    """Pergunta ao registry onde está o serviço `name`. Devolve o URL ou None."""
    try:
        r = requests.get(f"{REGISTRY_URL}/services/{name}", timeout=2)
        if r.ok:
            return r.json()["url"]
    except requests.RequestException:
        pass
    return None