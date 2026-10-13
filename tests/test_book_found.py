import json

import pytest

from schedagent.calendar import Calendar
from schedagent.rules import Booking
from schedagent.slots import Block
from schedagent.tools import SOLVER2_TOOLS, SOLVER_TOOLS, Session

MON = 0
BOTH = ["Ravi", "Meera"]


@pytest.fixture
def session():
    calendar = Calendar(
        {
            "Ravi": [Block(day=MON, start=0, length=2)],  # Mon 9:00-10:00
            "Meera": [Block(day=MON, start=4, length=1)],  # Mon 11:00-11:30
            "Tara": [],
        }
    )
    return Session(calendar, SOLVER2_TOOLS)


def find(session, **changes):
    args = {"attendees": BOTH, "duration_minutes": 60, "days": ["Monday"], **changes}
    return json.loads(session.call("find_slots", args))


def book(session, start="10:00", end="11:00", attendees=BOTH, day="Monday"):
    return session.call(
        "book", {"attendees": attendees, "day": day, "start": start, "end": end}
    )


def test_a_slot_the_search_returned_can_be_booked(session):
    assert find(session, latest_end="12:00")["slots"] == [
        {"day": "Monday", "start": "10:00", "end": "11:00"}
    ]
    assert book(session) == "Booked."
    assert session.booking == Booking(
        attendees=BOTH, block=Block(day=MON, start=2, length=2)
    )


def test_booking_before_any_search_is_refused(session):
    assert book(session) == (
        "Error: call find_slots first, then book a slot it returns"
    )
    assert not session.finished


def test_booking_after_a_search_that_found_nothing_is_refused(session):
    assert find(session, latest_end="10:00")["count"] == 0
    reply = book(session)
    assert reply.startswith("Error: the last find_slots found no slot")
    assert "give_up" in reply
    assert not session.finished


def test_a_time_the_search_did_not_return_is_refused(session):
    find(session, latest_end="12:00")
    for start, end in [("09:00", "10:00"), ("10:00", "11:30"), ("10:30", "11:00")]:
        reply = book(session, start, end)
        assert reply.startswith("Error: that is not a slot the last find_slots returned")
    assert book(session, day="Tuesday").startswith("Error: that is not a slot")
    assert not session.finished


def test_a_slot_found_for_other_people_is_refused(session):
    find(session, latest_end="12:00")
    assert book(session, attendees=["Ravi", "Tara"]).startswith(
        "Error: that is not a slot"
    )
    # The same people in another order are the same people.
    assert book(session, attendees=["Meera", "Ravi"]) == "Booked."


def test_only_the_last_search_counts(session):
    find(session, latest_end="12:00")
    find(session, earliest_start="16:00")
    assert book(session).startswith("Error: that is not a slot")
    assert book(session, "16:00", "17:00") == "Booked."


def test_a_search_that_fails_does_not_replace_the_last_one(session):
    find(session, latest_end="12:00")
    assert session.call("find_slots", {"attendees": BOTH}).startswith("Error:")
    assert book(session) == "Booked."


def test_a_found_slot_beyond_the_ones_shown_can_be_booked(session):
    result = find(session, attendees=["Tara"], days=["Friday"], duration_minutes=30)
    assert result["count"] == 16
    assert {"day": "Friday", "start": "16:30", "end": "17:00"} not in result["slots"]
    assert book(session, "16:30", "17:00", ["Tara"], "Friday") == "Booked."


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"day": "Someday"}, "'Someday' is not a day from Monday to Friday"),
        ({"start": "10:15"}, "'10:15' is not a time between 09:00 and 17:00"),
        ({"attendees": ["Ravi", "Zoya"]}, "unknown person: Zoya"),
        ({"start": "11:00", "end": "10:00"}, "that is not a slot"),
    ],
)
def test_a_badly_written_booking_is_still_an_error(session, changes, message):
    find(session, latest_end="12:00")
    args = {"attendees": BOTH, "day": "Monday", "start": "10:00", "end": "11:00"}
    reply = session.call("book", {**args, **changes})
    assert reply.startswith("Error: ")
    assert message in reply


def test_the_first_solver_agent_can_still_book_any_time():
    session = Session(Calendar({"Ravi": [], "Meera": []}), SOLVER_TOOLS)
    assert book(session) == "Booked."
