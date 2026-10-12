"""Honest uncertainty for a result measured on a limited number of tasks."""

import random
from statistics import mean


def bootstrap_interval(
    values: list[float], resamples: int = 10_000, level: float = 0.95, seed: int = 0
) -> tuple[float, float]:
    """A confidence interval for the mean of `values`, by resampling.

    Each resample draws as many values as there are, with replacement, and
    takes their mean. That imitates running the experiment again on a fresh
    set of tasks of the same kind. The interval is the range that holds the
    middle `level` of those means.
    """
    rng = random.Random(seed)
    size = len(values)
    means = sorted(mean(rng.choices(values, k=size)) for _ in range(resamples))
    low = means[int((1 - level) / 2 * resamples)]
    high = means[int((1 + level) / 2 * resamples) - 1]
    return low, high


def correct_rate(records: list[dict]) -> tuple[float, tuple[float, float]]:
    """The share of tasks graded correct, with its confidence interval."""
    scores = [float(record["grade"] == "correct") for record in records]
    return mean(scores), bootstrap_interval(scores)


def paired_difference(
    first: list[dict], second: list[dict]
) -> tuple[float, tuple[float, float]]:
    """How much more often `second` was correct than `first`, on the same tasks.

    The difference is taken task by task, so that a task both runs found easy
    or both found hard does not blur the comparison.
    """
    by_seed = {record["seed"]: record for record in first}
    if sorted(by_seed) != sorted(record["seed"] for record in second):
        raise ValueError("the two runs are not on the same tasks")
    gains = [
        float(record["grade"] == "correct")
        - float(by_seed[record["seed"]]["grade"] == "correct")
        for record in second
    ]
    return mean(gains), bootstrap_interval(gains)
