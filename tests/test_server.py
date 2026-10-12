import pytest

from schedagent.server import _wait_until_ready, running_ollama


class FakeServer:
    def __init__(self, exit_code=None):
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code


class FakeClient:
    """Refuses the connection a set number of times, then answers."""

    def __init__(self, refusals):
        self.refusals = refusals
        self.calls = 0

    def list(self):
        self.calls += 1
        if self.calls <= self.refusals:
            raise ConnectionError("not up yet")


def test_missing_ollama_is_reported_clearly(tmp_path):
    with pytest.raises(FileNotFoundError, match="Ollama is not unpacked"):
        with running_ollama(folder=tmp_path):
            pass


def test_waits_until_ollama_answers():
    client = FakeClient(refusals=2)
    _wait_until_ready(client, FakeServer(), timeout=5)
    assert client.calls == 3


def test_gives_up_if_ollama_stops_while_starting():
    with pytest.raises(RuntimeError, match="stopped while starting"):
        _wait_until_ready(FakeClient(refusals=0), FakeServer(exit_code=1), timeout=5)


def test_gives_up_if_ollama_never_answers():
    with pytest.raises(TimeoutError):
        _wait_until_ready(FakeClient(refusals=10**9), FakeServer(), timeout=0.6)
