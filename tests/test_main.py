from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import schedagent.__main__ as cli


class FakeClient:
    def __init__(self):
        self.pulled = []

    def pull(self, model):
        self.pulled.append(model)

    def list(self):
        models = [SimpleNamespace(model=name, size=1.93e9) for name in self.pulled]
        return SimpleNamespace(models=models)


def test_pull_downloads_the_named_model(monkeypatch, capsys):
    client = FakeClient()

    @contextmanager
    def fake_ollama():
        yield client

    monkeypatch.setattr(cli, "running_ollama", fake_ollama)
    cli.main(["pull", "some-model"])
    assert client.pulled == ["some-model"]
    assert "some-model: 1.93 GB" in capsys.readouterr().out


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])
