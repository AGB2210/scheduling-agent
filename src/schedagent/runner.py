"""Run the agent on a set of tasks and save what happened, one line per task."""

import json
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from schedagent.agent import LLM, run_agent
from schedagent.generator import Task, make_task
from schedagent.grading import grade
from schedagent.solver import preferred_blocks, valid_blocks
from schedagent.tools import Session
from schedagent.versions import PLAIN, Version


def run_task(task: Task, llm: LLM, max_turns: int, version: Version = PLAIN) -> dict:
    """Run one task and return a record of the run, ready to save."""
    session = Session(task.calendar, version.tools)
    started = time.perf_counter()
    trace = run_agent(
        task.request, session, llm, max_turns, system_prompt=version.system_prompt
    )
    seconds = time.perf_counter() - started
    result = grade(task, session)
    valid = valid_blocks(task.rules, task.calendar)
    return {
        "seed": task.seed,
        "request": task.request,
        "possible": bool(valid),
        "valid_slots": len(valid),
        "preferred_slots": len(preferred_blocks(task.rules, task.calendar)),
        "outcome": trace.outcome,
        "grade": result.kind,
        "problems": list(result.problems),
        "kept_preference": result.kept_preference,
        "llm_calls": trace.llm_calls,
        "seconds": round(seconds, 2),
        "steps": [
            {"tool": step.tool, "args": step.args, "result": step.result}
            for step in trace.steps
        ],
        # The first message is the system prompt, saved once in the header.
        "messages": list(trace.messages[1:]),
    }


def run_set(
    seeds: Iterable[int],
    llm: LLM,
    settings: dict,
    out: Path,
    max_turns: int = 12,
    on_task: Callable[[dict], None] = lambda record: None,
    version: Version = PLAIN,
) -> int:
    """Run every seed not already in `out`. Returns how many tasks were run.

    The file starts with one header line describing the run: `settings` (the
    model's name and options), the agent version with its tools and system
    prompt, and the turn limit. A run that was interrupted can be continued by
    calling this again with the same file. `on_task` is called with each new
    record, for showing progress.
    """
    header = {
        **settings,
        "agent": version.name,
        "tools": sorted(version.tools),
        "max_turns": max_turns,
        "system_prompt": version.system_prompt,
    }
    done = set()
    if out.exists():
        saved_header, records = load_run(out)
        if saved_header != header:
            raise ValueError(f"{out} was made with different settings")
        done = {record["seed"] for record in records}
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        _append(out, {"header": header})
    ran = 0
    for seed in seeds:
        if seed in done:
            continue
        record = run_task(make_task(seed), llm, max_turns, version)
        _append(out, record)
        on_task(record)
        ran += 1
    return ran


def load_run(path: Path) -> tuple[dict, list[dict]]:
    """Read a saved run back as its header and its task records."""
    lines = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]
    return lines[0]["header"], lines[1:]


def _append(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
