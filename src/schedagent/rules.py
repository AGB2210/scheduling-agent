"""The rules a booking must follow, and the checker that grades one."""

from pydantic import BaseModel, Field, model_validator

from schedagent.calendar import Calendar
from schedagent.slots import DAYS, SLOTS_PER_DAY, Block

ALL_DAYS = frozenset(range(len(DAYS)))


class Window(BaseModel, frozen=True):
    """The days and hours a meeting may fall in."""

    days: frozenset[int] = ALL_DAYS
    earliest: int = Field(default=0, ge=0, lt=SLOTS_PER_DAY)
    latest: int = Field(default=SLOTS_PER_DAY, gt=0, le=SLOTS_PER_DAY)

    @model_validator(mode="after")
    def _makes_sense(self):
        if not self.days or not self.days <= ALL_DAYS:
            raise ValueError("days must be a non-empty set of weekdays")
        if self.earliest >= self.latest:
            raise ValueError("earliest must come before latest")
        return self

    def allows_day(self, block: Block) -> bool:
        return block.day in self.days

    def allows_hours(self, block: Block) -> bool:
        return self.earliest <= block.start and block.end <= self.latest

    def allows(self, block: Block) -> bool:
        return self.allows_day(block) and self.allows_hours(block)


class MeetingRules(BaseModel, frozen=True):
    """What the person asking really wants. The agent never sees this."""

    attendees: frozenset[str] = Field(min_length=1)
    length: int = Field(gt=0, le=SLOTS_PER_DAY)
    must: Window = Window()
    prefer: Window | None = None


class Booking(BaseModel, frozen=True):
    """What the agent actually booked."""

    attendees: frozenset[str]
    block: Block


class Verdict(BaseModel, frozen=True):
    """The grade for one booking."""

    problems: tuple[str, ...]
    keeps_preference: bool

    @property
    def valid(self) -> bool:
        return not self.problems


def check(rules: MeetingRules, calendar: Calendar, booking: Booking) -> Verdict:
    """Grade a booking against the hidden rules and the calendar."""
    block = booking.block
    problems = []
    if booking.attendees != rules.attendees:
        problems.append("wrong attendees")
    if block.length != rules.length:
        problems.append("wrong length")
    if not rules.must.allows_day(block):
        problems.append("day not allowed")
    if not rules.must.allows_hours(block):
        problems.append("hours not allowed")
    for person in sorted(rules.attendees):
        if not calendar.is_free(person, block):
            problems.append(f"{person} is busy")
    keeps_preference = rules.prefer is None or rules.prefer.allows(block)
    return Verdict(problems=tuple(problems), keeps_preference=keeps_preference)
