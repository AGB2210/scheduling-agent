import pytest
from pydantic import ValidationError

from schedagent.slots import Block, slot_to_time, time_to_slot


def test_slot_to_time():
    assert slot_to_time(0) == "09:00"
    assert slot_to_time(10) == "14:00"
    assert slot_to_time(15) == "16:30"


def test_time_to_slot_undoes_slot_to_time():
    for slot in range(17):  # 17:00 is slot 16, the latest a block can end
        assert time_to_slot(slot_to_time(slot)) == slot


def test_time_to_slot_accepts_a_single_digit_hour():
    assert time_to_slot("9:30") == 1


@pytest.mark.parametrize("text", ["08:30", "17:30", "14:15", "2pm", "14", ""])
def test_time_to_slot_rejects_times_off_the_grid(text):
    with pytest.raises(ValueError):
        time_to_slot(text)


def test_block_slots_leave_out_the_end():
    block = Block(day=0, start=10, length=3)  # Mon 14:00-15:30
    assert list(block.slots()) == [10, 11, 12]


def test_back_to_back_blocks_do_not_clash():
    first = Block(day=0, start=0, length=2)  # 9:00-10:00
    second = Block(day=0, start=2, length=1)  # 10:00-10:30
    assert not first.clashes_with(second)
    assert not second.clashes_with(first)


def test_overlapping_blocks_clash():
    first = Block(day=0, start=0, length=2)  # 9:00-10:00
    second = Block(day=0, start=1, length=2)  # 9:30-10:30
    assert first.clashes_with(second)
    assert second.clashes_with(first)


def test_block_inside_another_clashes():
    outer = Block(day=2, start=4, length=6)
    inner = Block(day=2, start=6, length=1)
    assert outer.clashes_with(inner)
    assert inner.clashes_with(outer)


def test_same_time_on_different_days_does_not_clash():
    monday = Block(day=0, start=4, length=2)
    tuesday = Block(day=1, start=4, length=2)
    assert not monday.clashes_with(tuesday)


def test_block_may_end_exactly_at_close():
    block = Block(day=4, start=14, length=2)  # Fri 16:00-17:00
    assert block.end == 16


@pytest.mark.parametrize(
    "fields",
    [
        {"day": 5, "start": 0, "length": 1},  # no Saturday
        {"day": -1, "start": 0, "length": 1},
        {"day": 0, "start": 16, "length": 1},  # starts at 17:00
        {"day": 0, "start": 0, "length": 0},  # no time at all
        {"day": 0, "start": 15, "length": 2},  # runs to 17:30
    ],
)
def test_impossible_blocks_are_rejected(fields):
    with pytest.raises(ValidationError):
        Block(**fields)
