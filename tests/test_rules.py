import pytest
from pydantic import ValidationError

from schedagent.calendar import Calendar
from schedagent.rules import Booking, MeetingRules, Window, check
from schedagent.slots import Block

MON, TUE, WED, THU, FRI = range(5)


@pytest.fixture
def calendar():
    return Calendar(
        {
            "Ravi": [Block(day=MON, start=0, length=2)],  # Mon 9:00-10:00
            "Meera": [Block(day=TUE, start=10, length=2)],  # Tue 14:00-15:00
        }
    )


@pytest.fixture
def rules():
    # 30 minutes with Ravi and Meera, not Friday, mornings preferred.
    return MeetingRules(
        attendees={"Ravi", "Meera"},
        length=1,
        must=Window(days={MON, TUE, WED, THU}),
        prefer=Window(latest=6),  # over by 12:00
    )


def book(day, start, length=1, attendees=("Ravi", "Meera")):
    return Booking(
        attendees=attendees, block=Block(day=day, start=start, length=length)
    )


def test_good_morning_slot_is_valid_and_preferred(rules, calendar):
    verdict = check(rules, calendar, book(MON, 2))  # Mon 10:00
    assert verdict.valid
    assert verdict.problems == ()
    assert verdict.keeps_preference


def test_afternoon_slot_is_valid_but_not_preferred(rules, calendar):
    verdict = check(rules, calendar, book(MON, 10))  # Mon 14:00
    assert verdict.valid
    assert not verdict.keeps_preference


def test_forbidden_day_is_a_problem(rules, calendar):
    verdict = check(rules, calendar, book(FRI, 2))
    assert not verdict.valid
    assert verdict.problems == ("day not allowed",)


def test_busy_attendee_is_a_problem(rules, calendar):
    verdict = check(rules, calendar, book(MON, 1))  # Mon 9:30, Ravi busy
    assert verdict.problems == ("Ravi is busy",)


def test_wrong_length_is_a_problem(rules, calendar):
    verdict = check(rules, calendar, book(WED, 2, length=2))
    assert verdict.problems == ("wrong length",)


def test_missing_attendee_is_a_problem(rules, calendar):
    verdict = check(rules, calendar, book(WED, 2, attendees=("Ravi",)))
    assert verdict.problems == ("wrong attendees",)


def test_made_up_attendee_is_a_problem_not_a_crash(rules, calendar):
    booking = book(WED, 2, attendees=("Ravi", "Meera", "Zoya"))
    assert check(rules, calendar, booking).problems == ("wrong attendees",)


def test_every_problem_is_reported(rules, calendar):
    verdict = check(rules, calendar, book(FRI, 2, length=2))
    assert verdict.problems == ("wrong length", "day not allowed")


def test_hours_outside_the_window_are_a_problem(calendar):
    rules = MeetingRules(
        attendees={"Meera"}, length=2, must=Window(earliest=2, latest=8)
    )  # between 10:00 and 13:00
    ends_too_late = book(WED, 7, length=2, attendees=("Meera",))  # 12:30-13:30
    assert check(rules, calendar, ends_too_late).problems == ("hours not allowed",)
    just_fits = book(WED, 6, length=2, attendees=("Meera",))  # 12:00-13:00
    assert check(rules, calendar, just_fits).valid


def test_no_preference_counts_as_kept(calendar):
    rules = MeetingRules(attendees={"Meera"}, length=1)
    verdict = check(rules, calendar, book(MON, 12, attendees=("Meera",)))
    assert verdict.valid
    assert verdict.keeps_preference


@pytest.mark.parametrize(
    "fields",
    [
        {"days": set()},
        {"days": {7}},
        {"earliest": 6, "latest": 6},
        {"earliest": 8, "latest": 4},
    ],
)
def test_impossible_windows_are_rejected(fields):
    with pytest.raises(ValidationError):
        Window(**fields)


def test_rules_need_at_least_one_attendee():
    with pytest.raises(ValidationError):
        MeetingRules(attendees=set(), length=1)
