"""Helpers for the study notebooks: import an example by path and run its servers in the background."""
import asyncio
import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(rel: str):
    """Import an example file, e.g. load('01-modbus-tcp-basics/client.py')."""
    path = ROOT / rel
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"{path.parent.name[:2]}_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def port_open(port: int, host: str = "localhost") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def run_in_background(coro_factory, port: int, timeout: float = 20) -> None:
    """Start an asyncio server in a daemon thread and wait until its port answers."""
    if port_open(port):
        print(f"porta {port} já está ativa, reutilizando o servidor")
        return
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: loop.run_until_complete(coro_factory()), daemon=True).start()
    t_end = time.time() + timeout
    while time.time() < t_end:
        if port_open(port):
            print(f"servidor ativo na porta {port}")
            return
        time.sleep(0.2)
    raise TimeoutError(f"servidor não respondeu na porta {port}")


def require_broker(port: int = 1883) -> None:
    if not port_open(port):
        raise RuntimeError("Nenhum broker MQTT em localhost:1883. Rode 'docker compose up -d' na raiz do repositório.")
    print("broker MQTT encontrado em localhost:1883")
