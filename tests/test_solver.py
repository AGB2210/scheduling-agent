from schedagent.calendar import Calendar
from schedagent.rules import MeetingRules, Window
from schedagent.solver import preferred_blocks, valid_blocks
from schedagent.slots import Block

MON, TUE, WED, THU, FRI = range(5)


def test_finds_the_only_slot_that_works():
    calendar = Calendar(
        {
            "Ravi": [Block(day=MON, start=0, length=2)],  # Mon 9:00-10:00
            "Meera": [Block(day=MON, start=4, length=1)],  # Mon 11:00-11:30
        }
    )
    # One hour with both, Monday, between 9:00 and 12:00.
    rules = MeetingRules(
        attendees={"Ravi", "Meera"}, length=2, must=Window(days={MON}, latest=6)
    )
    assert valid_blocks(rules, calendar) == [Block(day=MON, start=2, length=2)]


def test_no_slot_works_gives_an_empty_list():
    calendar = Calendar({"Ravi": [Block(day=MON, start=0, length=16)]})
    rules = MeetingRules(attendees={"Ravi"}, length=1, must=Window(days={MON}))
    assert valid_blocks(rules, calendar) == []


def test_free_week_with_no_limits_has_all_80_slots():
    calendar = Calendar({"Meera": []})
    rules = MeetingRules(attendees={"Meera"}, length=1)
    blocks = valid_blocks(rules, calendar)
    assert len(blocks) == 80
    assert blocks[0] == Block(day=MON, start=0, length=1)
    assert blocks[-1] == Block(day=FRI, start=15, length=1)


def test_full_day_meeting_has_one_slot_per_day():
    calendar = Calendar({"Meera": []})
    rules = MeetingRules(attendees={"Meera"}, length=16)
    assert valid_blocks(rules, calendar) == [
        Block(day=day, start=0, length=16) for day in range(5)
    ]


def test_preferred_blocks_are_the_valid_ones_inside_the_preference():
    calendar = Calendar({"Meera": []})
    rules = MeetingRules(
        attendees={"Meera"},
        length=1,
        must=Window(days={WED}),
        prefer=Window(latest=2),  # over by 10:00
    )
    assert len(valid_blocks(rules, calendar)) == 16
    assert preferred_blocks(rules, calendar) == [
        Block(day=WED, start=0, length=1),
        Block(day=WED, start=1, length=1),
    ]


def test_preference_can_be_impossible_while_the_task_is_not():
    calendar = Calendar({"Meera": [Block(day=WED, start=0, length=2)]})
    rules = MeetingRules(
        attendees={"Meera"},
        length=1,
        must=Window(days={WED}),
        prefer=Window(latest=2),
    )
    assert len(valid_blocks(rules, calendar)) == 14
    assert preferred_blocks(rules, calendar) == []


def test_without_a_preference_every_valid_block_is_preferred():
    calendar = Calendar({"Ravi": [Block(day=TUE, start=3, length=4)]})
    rules = MeetingRules(attendees={"Ravi"}, length=2, must=Window(days={TUE, THU}))
    assert preferred_blocks(rules, calendar) == valid_blocks(rules, calendar)
