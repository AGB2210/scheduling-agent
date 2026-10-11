import os
import subprocess
import sys
from pathlib import Path

import pytest

import schedagent
from schedagent.generator import make_task
from schedagent.slots import DAYS, SLOTS_PER_DAY, Block

SEEDS = range(200)


def every_block(length):
    return [
        Block(day=day, start=start, length=length)
        for day in range(len(DAYS))
        for start in range(SLOTS_PER_DAY - length + 1)
    ]


def test_same_seed_gives_the_same_task():
    assert make_task(7) == make_task(7)


def test_different_seeds_give_different_tasks():
    assert make_task(7) != make_task(8)


@pytest.mark.parametrize("seed", SEEDS)
def test_attendees_are_two_or_three_people_from_the_calendar(seed):
    task = make_task(seed)
    assert 2 <= len(task.rules.attendees) <= 3
    assert task.rules.attendees <= set(task.calendar.people)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_persons_busy_blocks_never_overlap(seed):
    calendar = make_task(seed).calendar
    for person in calendar.people:
        blocks = calendar.busy(person)
        for i, first in enumerate(blocks):
            for second in blocks[i + 1 :]:
                assert not first.clashes_with(second)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_preference_can_be_kept_and_can_be_broken(seed):
    rules = make_task(seed).rules
    if rules.prefer is None:
        return
    allowed = [b for b in every_block(rules.length) if rules.must.allows(b)]
    kept = [b for b in allowed if rules.prefer.allows(b)]
    assert kept, "the hard rules leave no room for the preference"
    assert len(kept) < len(allowed), "the preference rules nothing out"


def test_tasks_do_not_depend_on_pythons_hash_seed():
    # Sets of names are ordered differently from one Python run to the next.
    # A task must not change because of that.
    script = (
        "from schedagent.generator import make_task\n"
        "for seed in range(20):\n"
        "    task = make_task(seed)\n"
        "    people = task.calendar.people\n"
        "    print(sorted(task.rules.attendees), task.rules.length,\n"
        "          sorted(task.rules.must.days), task.rules.must.earliest,\n"
        "          task.rules.must.latest,\n"
        "          task.rules.prefer and sorted(task.rules.prefer.days),\n"
        "          [(p, task.calendar.busy(p)) for p in people])\n"
    )
    src = str(Path(schedagent.__file__).parents[1])
    outputs = []
    for hash_seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": src}
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].strip()
