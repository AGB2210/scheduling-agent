import pytest

from schedagent.generator import make_task
from schedagent.request import write_request
from schedagent.rules import ALL_DAYS, MeetingRules, Window
from schedagent.slots import DAY_NAMES

MON, TUE, WED, THU, FRI = range(5)
SEEDS = range(200)
SOFT_WORDS = ("Ideally", "If possible", "Preferably", "would be best")


class FirstChoice:
    """Stands in for the rng and always takes the first phrasing."""

    def choice(self, options):
        return options[0]

    def sample(self, options, k):
        return list(options)[:k]


def request_for(**fields):
    return write_request(MeetingRules(**fields), FirstChoice())


def test_request_with_no_limits_is_just_the_opening():
    assert request_for(attendees={"Ravi", "Meera"}, length=1) == (
        "Set up a meeting for Meera and Ravi. It should last 30 minutes."
    )


def test_three_attendees_are_joined_with_commas():
    text = request_for(attendees={"Ravi", "Meera", "Arjun"}, length=2)
    assert text == "Set up a meeting for Arjun, Meera and Ravi. It should last 1 hour."


def test_one_forbidden_day_and_a_morning_preference():
    text = request_for(
        attendees={"Ravi", "Meera"},
        length=1,
        must=Window(days={MON, TUE, WED, THU}),
        prefer=Window(latest=6),
    )
    assert text == (
        "Set up a meeting for Meera and Ravi. It should last 30 minutes. "
        "It can't be on Friday. Ideally it would be over by 12:00."
    )


def test_two_forbidden_days_are_both_named():
    text = request_for(attendees={"Ravi"}, length=1, must=Window(days={TUE, WED, THU}))
    assert text.endswith("It can't be on Monday or Friday.")


def test_three_forbidden_days_names_the_allowed_ones_instead():
    text = request_for(attendees={"Ravi"}, length=1, must=Window(days={TUE, WED}))
    assert text.endswith("It has to be on Tuesday or Wednesday.")


def test_hard_morning_gives_a_firm_end_time():
    text = request_for(attendees={"Ravi"}, length=1, must=Window(latest=6))
    assert text.endswith("It has to be finished by 12:00.")


def test_hard_afternoon_gives_a_firm_start_time():
    text = request_for(attendees={"Ravi"}, length=1, must=Window(earliest=8))
    assert text.endswith("It can't start before 13:00.")


def test_preferred_afternoon_and_preferred_day_use_soft_words():
    afternoon = request_for(
        attendees={"Ravi"}, length=1, prefer=Window(earliest=8)
    )
    assert afternoon.endswith("Ideally it would start at 13:00 or later.")
    wednesday = request_for(attendees={"Ravi"}, length=1, prefer=Window(days={WED}))
    assert wednesday.endswith("Ideally on Wednesday.")


@pytest.mark.parametrize("seed", SEEDS)
def test_request_names_the_attendees_and_nobody_else(seed):
    task = make_task(seed)
    for person in task.calendar.people:
        assert (person in task.request) == (person in task.rules.attendees)


@pytest.mark.parametrize("seed", SEEDS)
def test_soft_words_appear_only_when_there_is_a_preference(seed):
    task = make_task(seed)
    has_soft_word = any(word in task.request for word in SOFT_WORDS)
    assert has_soft_word == (task.rules.prefer is not None)


@pytest.mark.parametrize("seed", SEEDS)
def test_request_names_the_right_days(seed):
    task = make_task(seed)
    must, prefer = task.rules.must, task.rules.prefer
    forbidden = ALL_DAYS - must.days
    # One or two forbidden days are named; with three, the allowed days are.
    named = forbidden if len(forbidden) <= 2 else must.days
    if prefer is not None and prefer.days != ALL_DAYS:
        named = named | prefer.days
    for day, name in enumerate(DAY_NAMES):
        assert (name in task.request) == (day in named)


@pytest.mark.parametrize("seed", SEEDS)
def test_request_states_the_right_clock_times(seed):
    task = make_task(seed)
    windows = [task.rules.must]
    if task.rules.prefer is not None:
        windows.append(task.rules.prefer)
    assert ("12:00" in task.request) == any(w.latest == 6 for w in windows)
    assert ("13:00" in task.request) == any(w.earliest == 8 for w in windows)
