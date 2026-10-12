"""Start and stop the copy of Ollama that lives in the project folder."""

import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ollama import Client

OLLAMA_DIR = Path("ollama")  # inside the project folder
# Not Ollama's usual port, so we never talk to some other copy by mistake.
HOST = "127.0.0.1:11435"


@contextmanager
def running_ollama(folder: Path = OLLAMA_DIR, timeout: float = 60) -> Iterator[Client]:
    """Start Ollama, hand back a client for it, and stop it afterwards."""
    program = folder / "bin" / "ollama.exe"
    if not program.exists():
        raise FileNotFoundError(f"Ollama is not unpacked at {program}")
    home = (folder / "home").resolve()
    home.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "OLLAMA_HOST": HOST,
        "OLLAMA_MODELS": str((folder / "models").resolve()),
        # Ollama writes a key file to the user's home folder. Point it here
        # instead, so nothing lands outside the project.
        "USERPROFILE": str(home),
        "HOME": str(home),
    }
    with open(folder / "server.log", "w") as log:
        server = subprocess.Popen(
            [str(program), "serve"], env=env, stdout=log, stderr=subprocess.STDOUT
        )
        try:
            client = Client(host=f"http://{HOST}")
            _wait_until_ready(client, server, timeout)
            yield client
        finally:
            _stop(server)


def _wait_until_ready(client: Client, server: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Ollama stopped while starting; see ollama/server.log")
        try:
            client.list()
            return
        except ConnectionError:
            time.sleep(0.25)
    raise TimeoutError(f"Ollama did not answer within {timeout} seconds")


def _stop(server: subprocess.Popen) -> None:
    """Stop Ollama and the model runner it starts, so no GPU memory stays held."""
    if server.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(server.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    server.wait(timeout=30)
