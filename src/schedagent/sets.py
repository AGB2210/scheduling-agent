"""Which generated tasks belong to which set."""

from schedagent.generator import make_task
from schedagent.solver import valid_blocks

PRACTICE_START = 1000


def practice_seeds(possible: int = 80, impossible: int = 20) -> list[int]:
    """Seeds for the practice set, counting up from 1000.

    Impossible tasks are rare, so taking seeds in order would give almost none.
    Instead this keeps the first `possible` tasks that have a valid slot and the
    first `impossible` tasks that have none.
    """
    wanted = {True: possible, False: impossible}
    chosen: dict[bool, list[int]] = {True: [], False: []}
    seed = PRACTICE_START
    while any(len(chosen[kind]) < wanted[kind] for kind in wanted):
        task = make_task(seed)
        kind = bool(valid_blocks(task.rules, task.calendar))
        if len(chosen[kind]) < wanted[kind]:
            chosen[kind].append(seed)
        seed += 1
    return sorted(chosen[True] + chosen[False])
