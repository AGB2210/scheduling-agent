"""Find every booking that follows the rules, by trying them all."""

from schedagent.calendar import Calendar
from schedagent.rules import Booking, MeetingRules, Verdict, check
from schedagent.slots import DAYS, SLOTS_PER_DAY, Block


def _candidates(rules: MeetingRules) -> list[Block]:
    """Every block of the right length that fits inside a working day."""
    last_start = SLOTS_PER_DAY - rules.length
    return [
        Block(day=day, start=start, length=rules.length)
        for day in range(len(DAYS))
        for start in range(last_start + 1)
    ]


def _grade(rules: MeetingRules, calendar: Calendar, block: Block) -> Verdict:
    return check(rules, calendar, Booking(attendees=rules.attendees, block=block))


def valid_blocks(rules: MeetingRules, calendar: Calendar) -> list[Block]:
    """Blocks that break no hard rule, in day then time order."""
    return [
        block for block in _candidates(rules) if _grade(rules, calendar, block).valid
    ]


def preferred_blocks(rules: MeetingRules, calendar: Calendar) -> list[Block]:
    """Valid blocks that also keep the preference."""
    return [
        block
        for block in valid_blocks(rules, calendar)
        if _grade(rules, calendar, block).keeps_preference
    ]
