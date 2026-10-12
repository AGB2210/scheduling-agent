from schedagent.generator import make_task
from schedagent.sets import PRACTICE_START, practice_seeds
from schedagent.solver import valid_blocks


def is_possible(seed):
    task = make_task(seed)
    return bool(valid_blocks(task.rules, task.calendar))


def test_practice_set_is_80_possible_and_20_impossible_tasks():
    seeds = practice_seeds()
    assert len(seeds) == len(set(seeds)) == 100
    assert seeds == sorted(seeds)
    assert min(seeds) >= PRACTICE_START
    assert sum(is_possible(seed) for seed in seeds) == 80


def test_the_mix_can_be_chosen():
    seeds = practice_seeds(possible=3, impossible=1)
    assert [is_possible(seed) for seed in seeds].count(True) == 3
    assert len(seeds) == 4


def test_practice_set_has_not_changed():
    # If this fails, the generator now makes different tasks for the same
    # seeds, and earlier runs can no longer be compared with new ones.
    seeds = practice_seeds()
    assert seeds[:5] == [1000, 1001, 1002, 1003, 1004]
    assert seeds[-5:] == [1580, 1681, 1715, 1719, 1729]
    assert make_task(1000).request == (
        "Please book an hour and a half for a meeting between Divya, Ravi and "
        "Meera. Tuesday is out. It must be over by 12:00. Friday would be best "
        "if it works."
    )
