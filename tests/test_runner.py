import json

import pytest

from schedagent.agent import SYSTEM_PROMPT, Reply, ToolCall
from schedagent.generator import make_task
from schedagent.runner import load_run, run_set, run_task
from schedagent.slots import DAY_NAMES, slot_to_time
from schedagent.solver import valid_blocks


SETTINGS = {"model": "fake-model", "options": {"seed": 0}}


def give_up(messages):
    return Reply(calls=(ToolCall("give_up", {"reason": "no time works"}),))


def solver_copier(seed):
    """A fake model that books the solver's first answer for one task."""
    task = make_task(seed)
    block = valid_blocks(task.rules, task.calendar)[0]
    args = {
        "attendees": sorted(task.rules.attendees),
        "day": DAY_NAMES[block.day],
        "start": slot_to_time(block.start),
        "end": slot_to_time(block.end),
    }
    return lambda messages: Reply(calls=(ToolCall("book", args),))


def test_run_task_records_a_correct_booking():
    record = run_task(make_task(0), solver_copier(0), max_turns=12)
    assert record["seed"] == 0
    assert record["request"] == make_task(0).request
    assert record["possible"] is True
    assert record["valid_slots"] > 0
    assert record["outcome"] == "booked"
    assert record["grade"] == "correct"
    assert record["problems"] == []
    assert record["llm_calls"] == 1
    assert [step["tool"] for step in record["steps"]] == ["book"]
    assert record["steps"][0]["result"] == "Booked."
    assert record["messages"][0] == {"role": "user", "content": make_task(0).request}
    json.dumps(record)  # everything in a record can be saved


def test_run_task_records_a_wrong_give_up():
    record = run_task(make_task(0), give_up, max_turns=12)
    assert record["outcome"] == "gave_up"
    assert record["grade"] == "gave_up_wrongly"


def test_run_set_saves_a_header_and_one_line_per_task(tmp_path):
    out = tmp_path / "runs" / "run.jsonl"
    ran = run_set([0, 1, 2], give_up, SETTINGS, out, max_turns=5)
    header, records = load_run(out)
    assert ran == 3
    assert header == {
        "model": "fake-model",
        "options": {"seed": 0},
        "max_turns": 5,
        "system_prompt": SYSTEM_PROMPT,
    }
    assert [record["seed"] for record in records] == [0, 1, 2]


def test_run_set_continues_an_interrupted_run(tmp_path):
    out = tmp_path / "run.jsonl"
    run_set([0, 1], give_up, SETTINGS, out)
    seen = []
    ran = run_set([0, 1, 2, 3], give_up, SETTINGS, out, on_task=seen.append)
    assert ran == 2
    assert [record["seed"] for record in seen] == [2, 3]
    assert [record["seed"] for record in load_run(out)[1]] == [0, 1, 2, 3]


def test_run_set_refuses_to_mix_two_different_runs_in_one_file(tmp_path):
    out = tmp_path / "run.jsonl"
    run_set([0], give_up, SETTINGS, out)
    with pytest.raises(ValueError, match="different settings"):
        run_set([1], give_up, {"model": "another-model"}, out)
