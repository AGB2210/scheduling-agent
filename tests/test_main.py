from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import schedagent.__main__ as cli
from schedagent.agent import Reply, ToolCall
from schedagent.runner import load_run
from schedagent.sets import practice_seeds
from schedagent.versions import SOLVER


class FakeClient:
    def __init__(self):
        self.pulled = []

    def pull(self, model):
        self.pulled.append(model)

    def list(self):
        models = [SimpleNamespace(model=name, size=1.93e9) for name in self.pulled]
        return SimpleNamespace(models=models)


@pytest.fixture
def client(monkeypatch):
    client = FakeClient()

    @contextmanager
    def fake_ollama():
        yield client

    monkeypatch.setattr(cli, "running_ollama", fake_ollama)
    return client


def always_gives_up(client, model, tools):
    return lambda messages: Reply(calls=(ToolCall("give_up", {"reason": "none"}),))


def test_pull_downloads_the_named_model(client, capsys):
    cli.main(["pull", "some-model"])
    assert client.pulled == ["some-model"]
    assert "some-model: 1.93 GB" in capsys.readouterr().out


def test_run_saves_the_first_practice_tasks_and_report_counts_them(
    client, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(cli, "local_model", always_gives_up)
    out = tmp_path / "run.jsonl"
    cli.main(["run", "--model", "some-model", "--out", str(out), "--limit", "3"])

    header, records = load_run(out)
    assert header["model"] == "some-model"
    assert header["agent"] == "plain"
    assert [record["seed"] for record in records] == practice_seeds()[:3]
    assert "Ran 3 tasks." in capsys.readouterr().out

    cli.main(["report", str(out)])
    report = capsys.readouterr().out
    assert "Model: some-model" in report
    assert "Agent: plain (book, get_busy, give_up)" in report
    assert "gave_up_wrongly" in report


def test_run_can_use_the_solver_version(client, monkeypatch, tmp_path):
    given = {}

    def records_its_tools(client, model, tools):
        given["tools"] = tools
        return always_gives_up(client, model, tools)

    monkeypatch.setattr(cli, "local_model", records_its_tools)
    out = tmp_path / "run.jsonl"
    cli.main(
        ["run", "--model", "m", "--out", str(out), "--limit", "1", "--agent", "solver"]
    )
    assert load_run(out)[0]["agent"] == "solver"
    assert given["tools"] is SOLVER.tools


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])
