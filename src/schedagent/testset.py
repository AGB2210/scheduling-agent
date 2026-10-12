"""The test set: generated calendars and rules, with requests written separately.

A worksheet lists each task's rules as plain facts. The author writes the request
for each one in their own words, and the filled-in worksheet is the test set.
"""

import re
from dataclasses import replace
from pathlib import Path

from schedagent.generator import NAMES, Task, make_task
from schedagent.rules import ALL_DAYS, MeetingRules, Window
from schedagent.slots import DAY_NAMES, SLOTS_PER_DAY, slot_to_time

WORKSHEET = Path("data") / "test" / "worksheet.txt"

LENGTHS = {1: "30 minutes", 2: "1 hour", 3: "90 minutes", 4: "2 hours"}

INSTRUCTIONS = """\
# Test set worksheet
#
# For each task below, write the request a real person would send, after
# "Request:". Use your own words, the way you would message a colleague.
#
# - Say everything listed: who, how long, and any limit on days or hours.
# - "Firm" limits must be followed. Make them sound firm.
# - A "wish" is optional. Make it sound like a preference, not a rule.
# - Do not copy the wording of the facts. Vary how you say things.
# - A request can run over more than one line.
#
# Lines that start with # are ignored.
"""


def describe(rules: MeetingRules) -> dict[str, str]:
    """State a task's rules as short facts for the person writing the request."""
    return {
        "Who": ", ".join(sorted(rules.attendees)),
        "Length": LENGTHS.get(rules.length, f"{rules.length * 30} minutes"),
        "Days (firm)": _days(rules.must),
        "Hours (firm)": " and ".join(_hours(rules.must, "must end by", "cannot start before"))
        or "any time",
        "Wish (optional)": _wish(rules.prefer),
    }


def _days(window: Window) -> str:
    forbidden = [DAY_NAMES[day] for day in sorted(ALL_DAYS - window.days)]
    if not forbidden:
        return "any day"
    if len(forbidden) <= 2:
        return ", ".join(f"not {day}" for day in forbidden)
    return "only " + ", ".join(DAY_NAMES[day] for day in sorted(window.days))


def _hours(window: Window, end_by: str, start_from: str) -> list[str]:
    facts = []
    if window.latest < SLOTS_PER_DAY:
        facts.append(f"{end_by} {slot_to_time(window.latest)}")
    if window.earliest > 0:
        facts.append(f"{start_from} {slot_to_time(window.earliest)}")
    return facts


def _wish(prefer: Window | None) -> str:
    if prefer is None:
        return "none"
    facts = _hours(prefer, "end by", "start at or after")
    if prefer.days != ALL_DAYS:
        facts.append("on " + " or ".join(DAY_NAMES[day] for day in sorted(prefer.days)))
    return " and ".join(facts)


def write_worksheet(path: Path, seeds: list[int]) -> None:
    """Create an empty worksheet. Never replaces one that already exists."""
    if path.exists():
        raise FileExistsError(f"{path} already exists and may hold written requests")
    blocks = [INSTRUCTIONS]
    for number, seed in enumerate(seeds, start=1):
        facts = describe(make_task(seed).rules)
        lines = [f"Task {number} of {len(seeds)} (seed {seed})"]
        lines += [f"  {name}: {value}" for name, value in facts.items()]
        lines.append("Request: ")
        blocks.append("\n".join(lines) + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(blocks), encoding="utf-8")


def read_worksheet(path: Path) -> dict[int, str]:
    """Read the request written for each seed. Unwritten ones are empty."""
    requests: dict[int, str] = {}
    seed = None
    writing = False
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("#"):
            continue
        header = re.match(r"Task \d+ of \d+ \(seed (\d+)\)", line)
        if header:
            seed = int(header[1])
            requests[seed] = ""
            writing = False
        elif seed is not None and line.startswith("Request:"):
            requests[seed] = line[len("Request:") :].strip()
            writing = True
        elif writing and line.strip():
            requests[seed] = f"{requests[seed]} {line.strip()}".strip()
    return requests


def check_worksheet(path: Path, seeds: list[int]) -> list[str]:
    """List anything that looks wrong, for the person who wrote it to review."""
    requests = read_worksheet(path)
    if sorted(requests) != sorted(seeds):
        return ["the worksheet's tasks are not the test set's tasks"]
    problems = []
    for number, seed in enumerate(seeds, start=1):
        text = requests[seed]
        attendees = make_task(seed).rules.attendees
        if not text:
            problems.append(f"Task {number}: no request written yet")
            continue
        for name in NAMES:
            named = re.search(rf"\b{name}\b", text, flags=re.IGNORECASE) is not None
            if name in attendees and not named:
                problems.append(f"Task {number}: does not mention {name}")
            if name not in attendees and named:
                problems.append(f"Task {number}: mentions {name}, who is not attending")
    return problems


def load_test_tasks(path: Path, seeds: list[int]) -> list[Task]:
    """The test tasks, each with the request written for it."""
    requests = read_worksheet(path)
    if sorted(requests) != sorted(seeds):
        raise ValueError("the worksheet's tasks are not the test set's tasks")
    unwritten = [seed for seed in seeds if not requests[seed]]
    if unwritten:
        raise ValueError(f"{len(unwritten)} requests have not been written yet")
    return [replace(make_task(seed), request=requests[seed]) for seed in seeds]
