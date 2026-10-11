import pytest

from schedagent.calendar import Calendar, UnknownPerson
from schedagent.slots import Block


@pytest.fixture
def calendar():
    return Calendar(
        {
            "Ravi": [
                Block(day=0, start=0, length=2),  # Mon 9:00-10:00
                Block(day=0, start=2, length=1),  # Mon 10:00-10:30
            ],
            "Meera": [],
        }
    )


def test_people_are_listed_in_order(calendar):
    assert calendar.people == ["Meera", "Ravi"]


def test_busy_returns_the_persons_blocks(calendar):
    assert calendar.busy("Ravi") == [
        Block(day=0, start=0, length=2),
        Block(day=0, start=2, length=1),
    ]


def test_not_free_during_a_busy_block(calendar):
    assert not calendar.is_free("Ravi", Block(day=0, start=1, length=2))


def test_free_right_after_a_busy_block(calendar):
    assert calendar.is_free("Ravi", Block(day=0, start=3, length=2))


def test_free_at_the_same_time_on_another_day(calendar):
    assert calendar.is_free("Ravi", Block(day=1, start=0, length=2))


def test_person_with_no_blocks_is_always_free(calendar):
    assert calendar.is_free("Meera", Block(day=0, start=0, length=16))


def test_unknown_person_is_an_error(calendar):
    with pytest.raises(UnknownPerson):
        calendar.busy("Zoya")
    with pytest.raises(UnknownPerson):
        calendar.is_free("Zoya", Block(day=0, start=0, length=1))


def test_changing_a_returned_list_does_not_change_the_calendar(calendar):
    calendar.busy("Meera").append(Block(day=0, start=0, length=1))
    assert calendar.busy("Meera") == []


def test_changing_the_input_does_not_change_the_calendar():
    blocks = []
    calendar = Calendar({"Meera": blocks})
    blocks.append(Block(day=0, start=0, length=1))
    assert calendar.busy("Meera") == []
