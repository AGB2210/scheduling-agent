import pytest

from schedagent.stats import bootstrap_interval, correct_rate, paired_difference


def records(*grades, first_seed=0):
    return [
        {"seed": first_seed + index, "grade": grade}
        for index, grade in enumerate(grades)
    ]


def test_interval_for_identical_values_has_no_width():
    assert bootstrap_interval([1.0] * 20) == (1.0, 1.0)
    assert bootstrap_interval([0.0] * 20) == (0.0, 0.0)


def test_interval_contains_the_mean_and_stays_between_0_and_1():
    values = [1.0] * 15 + [0.0] * 5
    low, high = bootstrap_interval(values)
    assert 0.0 <= low < 0.75 < high <= 1.0


def test_interval_is_the_same_every_time():
    values = [1.0] * 15 + [0.0] * 5
    assert bootstrap_interval(values) == bootstrap_interval(values)


def test_more_tasks_give_a_narrower_interval():
    few = bootstrap_interval([1.0] * 15 + [0.0] * 5)
    many = bootstrap_interval([1.0] * 150 + [0.0] * 50)
    assert many[1] - many[0] < few[1] - few[0]


def test_a_wider_level_gives_a_wider_interval():
    values = [1.0] * 15 + [0.0] * 5
    narrow = bootstrap_interval(values, level=0.5)
    wide = bootstrap_interval(values, level=0.95)
    assert wide[0] <= narrow[0] and narrow[1] <= wide[1]


def test_correct_rate_counts_only_correct_grades():
    rate, (low, high) = correct_rate(
        records("correct", "correct", "bad_booking", "no_answer")
    )
    assert rate == 0.5
    assert low <= 0.5 <= high


def test_paired_difference_compares_the_same_tasks():
    first = records("correct", "bad_booking", "bad_booking", "bad_booking")
    second = records("correct", "correct", "correct", "bad_booking")
    gain, (low, high) = paired_difference(first, second)
    assert gain == 0.5
    assert low <= 0.5 <= high


def test_paired_difference_matches_tasks_by_seed_not_by_order():
    first = records("correct", "bad_booking")
    second = list(reversed(records("bad_booking", "correct")))
    gain, _ = paired_difference(first, second)
    assert gain == 0.0  # one task was lost and one was gained


def test_paired_difference_can_be_negative():
    gain, (low, high) = paired_difference(
        records("correct", "correct"), records("bad_booking", "bad_booking")
    )
    assert (gain, low, high) == (-1.0, -1.0, -1.0)


def test_paired_difference_needs_the_same_tasks():
    with pytest.raises(ValueError, match="not on the same tasks"):
        paired_difference(records("correct"), records("correct", first_seed=5))
