import json

import pytest

from schedagent.calendar import Calendar
from schedagent.rules import Booking
from schedagent.slots import Block
from schedagent.tools import TOOLS, Session

MON, TUE = 0, 1


@pytest.fixture
def session():
    return Session(
        Calendar(
            {
                "Ravi": [Block(day=MON, start=0, length=2)],  # Mon 9:00-10:00
                "Meera": [],
            }
        )
    )


def book_args(**changes):
    args = {
        "attendees": ["Ravi", "Meera"],
        "day": "Tuesday",
        "start": "14:00",
        "end": "15:30",
    }
    return {**args, **changes}


def test_list_people(session):
    assert json.loads(session.call("list_people", {})) == ["Meera", "Ravi"]


def test_get_busy_shows_days_and_clock_times(session):
    assert json.loads(session.call("get_busy", {"person": "Ravi"})) == [
        {"day": "Monday", "start": "09:00", "end": "10:00"}
    ]
    assert json.loads(session.call("get_busy", {"person": "Meera"})) == []


def test_get_busy_for_a_made_up_person_is_an_error(session):
    assert session.call("get_busy", {"person": "Zoya"}) == "Error: unknown person: Zoya"
    assert not session.finished


def test_book_records_the_booking_and_finishes(session):
    assert session.call("book", book_args()) == "Booked."
    assert session.booking == Booking(
        attendees={"Ravi", "Meera"}, block=Block(day=TUE, start=10, length=3)
    )
    assert session.finished


@pytest.mark.parametrize("day", ["Tue", "tuesday", " TUESDAY "])
def test_book_accepts_short_and_long_day_names(session, day):
    session.call("book", book_args(day=day))
    assert session.booking.block.day == TUE


def test_book_may_end_at_closing_time(session):
    session.call("book", book_args(start="16:00", end="17:00"))
    assert session.booking.block == Block(day=TUE, start=14, length=2)


def test_book_does_not_refuse_a_clash(session):
    # Ravi is busy then. Spotting that is the agent's job, not the tool's.
    reply = session.call("book", book_args(day="Monday", start="09:30", end="10:30"))
    assert reply == "Booked."
    assert session.booking.block == Block(day=MON, start=1, length=2)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"attendees": ["Ravi", "Zoya"]}, "unknown person: Zoya"),
        ({"day": "Saturday"}, "'Saturday' is not a day from Monday to Friday"),
        ({"start": "14:15"}, "'14:15' is not a time between 09:00 and 17:00"),
        ({"start": "08:00"}, "'08:00' is not a time between 09:00 and 17:00"),
        ({"end": "17:30"}, "'17:30' is not a time between 09:00 and 17:00"),
        ({"start": "2pm"}, "'2pm' is not a time between 09:00 and 17:00"),
        ({"start": "15:30", "end": "14:00"}, "end must be after start"),
        ({"start": "14:00", "end": "14:00"}, "end must be after start"),
        ({"start": "17:00", "end": "17:00"}, "end must be after start"),
        ({"attendees": []}, "attendees: List should have at least 1 item"),
        ({"attendees": "Ravi"}, "attendees: Input should be a valid list"),
        ({"room": "A1"}, "room: Extra inputs are not permitted"),
    ],
)
def test_a_bad_booking_is_an_error_and_books_nothing(session, changes, message):
    reply = session.call("book", book_args(**changes))
    assert reply.startswith("Error: ")
    assert message in reply
    assert session.booking is None
    assert not session.finished


def test_a_missing_argument_is_named_in_the_error(session):
    args = book_args()
    del args["end"]
    assert session.call("book", args) == "Error: end: Field required"


def test_arguments_that_are_not_a_dict_are_an_error(session):
    assert session.call("get_busy", "Ravi").startswith("Error: ")


def test_a_made_up_tool_is_an_error(session):
    reply = session.call("delete_all", {})
    assert reply == "Error: there is no tool called 'delete_all'."
    assert not session.finished


def test_give_up_finishes_without_a_booking(session):
    assert session.call("give_up", {"reason": "nobody is free"}) == "Noted."
    assert session.gave_up
    assert session.booking is None
    assert session.finished


def test_nothing_runs_after_the_task_is_finished(session):
    session.call("book", book_args())
    reply = session.call("book", book_args(day="Monday"))
    assert reply == "Error: this task is already finished."
    assert session.booking.block.day == TUE


def test_every_tool_has_a_description():
    assert set(TOOLS) == {"list_people", "get_busy", "book", "give_up"}
    assert all(tool.description for tool in TOOLS.values())
