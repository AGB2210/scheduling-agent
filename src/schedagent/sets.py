"""Which generated tasks belong to which set."""

from schedagent.generator import make_task
from schedagent.solver import valid_blocks

PRACTICE_START = 1000
# Far from the practice seeds, so the two sets can never share a task.
HELD_OUT_START = 5000


def practice_seeds(possible: int = 80, impossible: int = 20) -> list[int]:
    """Seeds for the practice set, counting up from 1000."""
    return _pick_seeds(PRACTICE_START, possible, impossible)


def held_out_seeds(possible: int = 80, impossible: int = 20) -> list[int]:
    """Seeds for the test set, counting up from 5000.

    Only the calendars and rules come from these seeds. The requests in the
    test set are written separately.
    """
    return _pick_seeds(HELD_OUT_START, possible, impossible)


def _pick_seeds(start: int, possible: int, impossible: int) -> list[int]:
    """The first seeds from `start` that give the wanted mix of tasks.

    Impossible tasks are rare, so taking seeds in order would give almost none.
    Instead this keeps the first `possible` tasks that have a valid slot and the
    first `impossible` tasks that have none.
    """
    wanted = {True: possible, False: impossible}
    chosen: dict[bool, list[int]] = {True: [], False: []}
    seed = start
    while any(len(chosen[kind]) < wanted[kind] for kind in wanted):
        task = make_task(seed)
        kind = bool(valid_blocks(task.rules, task.calendar))
        if len(chosen[kind]) < wanted[kind]:
            chosen[kind].append(seed)
        seed += 1
    return sorted(chosen[True] + chosen[False])
