import asyncio
import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(rel: str, name: str | None = None):
    """Import an example by file path (folders start with digits, so no packages)."""
    path = ROOT / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name or path.stem + "_" + path.parent.name[:2], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def port_open(host, port) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_port(port, timeout=10):
    t = time.time() + timeout
    while time.time() < t:
        if port_open("localhost", port):
            return
        time.sleep(0.1)
    raise TimeoutError(port)


@pytest.fixture(scope="session")
def broker():
    if not port_open("localhost", 1883):
        pytest.skip("needs an MQTT broker on localhost:1883 (docker compose up -d)")


def _serve(coro_factory):
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: loop.run_until_complete(coro_factory()), daemon=True).start()


@pytest.fixture(scope="session")
def modbus_plant():
    plant = load("01-modbus-tcp-basics/plant_server.py")
    _serve(lambda: plant.main(port=5021))
    wait_port(5021)
    return 5021


@pytest.fixture(scope="session")
def opcua_server():
    srv = load("03-opcua-server-model/server.py")
    _serve(lambda: srv.main("opc.tcp://0.0.0.0:4842/iiot-examples/"))
    wait_port(4842, 20)
    time.sleep(1)
    return "opc.tcp://localhost:4842/iiot-examples/"
