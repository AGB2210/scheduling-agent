"""The tools the agent can call. They are its only view of the calendars."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from schedagent.calendar import Calendar
from schedagent.rules import Booking, MeetingRules, Window
from schedagent.slots import (
    DAY_NAMES,
    DAYS,
    SLOT_MINUTES,
    SLOTS_PER_DAY,
    Block,
    slot_to_time,
    time_to_slot,
)
from schedagent.solver import valid_blocks

MAX_SLOTS_SHOWN = 10


class ToolError(Exception):
    """A mistake in a tool call that the agent should be told about."""


class GetBusyArgs(BaseModel, extra="forbid"):
    person: str


class FindSlotsArgs(BaseModel, extra="forbid"):
    attendees: list[str] = Field(
        min_length=1, description="Everyone who must be at the meeting."
    )
    duration_minutes: int = Field(
        description="How long the meeting lasts, in minutes: 30, 60, 90 and so on."
    )
    days: list[str] | None = Field(
        default=None,
        description="The only days the meeting may be on, such as Monday. "
        "Leave out to allow every day from Monday to Friday.",
    )
    # People usually say which days are out, not which are allowed. Without
    # this, the model had to turn one list into the other and often got it wrong.
    excluded_days: list[str] | None = Field(
        default=None,
        description="Days the meeting must not be on. "
        "Use this when the request rules days out.",
    )
    earliest_start: str = Field(
        default="09:00", description="The meeting may not start before this time."
    )
    latest_end: str = Field(
        default="17:00", description="The meeting must be over by this time."
    )


class BookArgs(BaseModel, extra="forbid"):
    attendees: list[str] = Field(min_length=1)
    day: str
    start: str
    end: str


class GiveUpArgs(BaseModel, extra="forbid"):
    reason: str


class Session:
    """One task's calendars, plus whatever the agent ends up deciding."""

    def __init__(self, calendar: Calendar, tools: "dict[str, Tool] | None" = None):
        self.calendar = calendar
        self.tools = PLAIN_TOOLS if tools is None else tools
        self.booking: Booking | None = None
        self.gave_up = False

    @property
    def finished(self) -> bool:
        return self.booking is not None or self.gave_up

    def call(self, name: str, args: dict) -> str:
        """Run one tool call. A mistake comes back as an error message."""
        if self.finished:
            return "Error: this task is already finished."
        if name not in self.tools:
            return f"Error: there is no tool called {name!r}."
        tool = self.tools[name]
        try:
            return tool.run(self, tool.args.model_validate(args))
        except ValidationError as error:
            problems = [
                f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
                for problem in error.errors()
            ]
            return f"Error: {'; '.join(problems)}"
        except ToolError as error:
            return f"Error: {error}"

    def _get_busy(self, args: GetBusyArgs) -> str:
        self._require_known([args.person])
        return json.dumps(
            [
                {
                    "day": DAY_NAMES[block.day],
                    "start": slot_to_time(block.start),
                    "end": slot_to_time(block.end),
                }
                for block in self.calendar.busy(args.person)
            ]
        )

    def _find_slots(self, args: FindSlotsArgs) -> str:
        """Hand the rules the model stated to the solver."""
        self._require_known(args.attendees)
        blocks = valid_blocks(rules_from_search(args), self.calendar)
        return json.dumps(
            {
                "count": len(blocks),
                "slots": [
                    {
                        "day": DAY_NAMES[block.day],
                        "start": slot_to_time(block.start),
                        "end": slot_to_time(block.end),
                    }
                    for block in blocks[:MAX_SLOTS_SHOWN]
                ],
            }
        )

    def _book(self, args: BookArgs) -> str:
        # Like a real calendar, this does not refuse a clash.
        self._require_known(args.attendees)
        day = _parse_day(args.day)
        start, end = _parse_time(args.start), _parse_time(args.end)
        if end <= start:
            raise ToolError("end must be after start")
        block = Block(day=day, start=start, length=end - start)
        self.booking = Booking(attendees=args.attendees, block=block)
        return "Booked."

    def _give_up(self, args: GiveUpArgs) -> str:
        self.gave_up = True
        return "Noted."

    def _require_known(self, people: list[str]) -> None:
        unknown = [person for person in people if person not in self.calendar.people]
        if unknown:
            raise ToolError(f"unknown person: {', '.join(unknown)}")


def rules_from_search(args: FindSlotsArgs) -> MeetingRules:
    """Turn find_slots arguments into the rules the solver understands."""
    length, remainder = divmod(args.duration_minutes, SLOT_MINUTES)
    if remainder or not 1 <= length <= SLOTS_PER_DAY:
        raise ToolError("duration_minutes must be a multiple of 30, from 30 to 480")
    if args.days is not None and not args.days:
        raise ToolError("days must name at least one day, or be left out")
    allowed = {_parse_day(day) for day in (DAY_NAMES if args.days is None else args.days)}
    allowed -= {_parse_day(day) for day in args.excluded_days or []}
    if not allowed:
        raise ToolError("days and excluded_days together leave no day to search")
    earliest, latest = _parse_time(args.earliest_start), _parse_time(args.latest_end)
    if latest <= earliest:
        raise ToolError("latest_end must be after earliest_start")
    return MeetingRules(
        attendees=args.attendees,
        length=length,
        must=Window(days=allowed, earliest=earliest, latest=latest),
    )


def _parse_day(text: str) -> int:
    wanted = text.strip().lower()
    for names in (DAY_NAMES, DAYS):
        for day, name in enumerate(names):
            if name.lower() == wanted:
                return day
    raise ToolError(f"{text!r} is not a day from Monday to Friday")


def _parse_time(text: str) -> int:
    try:
        return time_to_slot(text)
    except ValueError as error:
        raise ToolError(str(error)) from None


@dataclass(frozen=True)
class Tool:
    description: str
    args: type[BaseModel]
    run: Callable[[Session, BaseModel], str]


# Every tool takes at least one argument. A tool with none (list_people, since
# removed) led the model to invent arguments, and then to copy that mistake
# into its later calls.
GET_BUSY = Tool(
    "Show when one person is busy this week.", GetBusyArgs, Session._get_busy
)
FIND_SLOTS = Tool(
    "Find the times this week when every attendee is free for a meeting of the "
    f"given length. Returns how many there are and the first {MAX_SLOTS_SHOWN}.",
    FindSlotsArgs,
    Session._find_slots,
)
BOOK = Tool(
    "Book the meeting. Times look like 14:00 and fall on the hour or half "
    "hour, between 09:00 and 17:00. This ends the task.",
    BookArgs,
    Session._book,
)
GIVE_UP = Tool(
    "Say that no time works for this meeting. This ends the task.",
    GiveUpArgs,
    Session._give_up,
)

# The plain agent reads calendars and works out a time itself.
PLAIN_TOOLS = {"get_busy": GET_BUSY, "book": BOOK, "give_up": GIVE_UP}
# The solver agent states the rules and lets the solver find the times.
SOLVER_TOOLS = {"find_slots": FIND_SLOTS, "book": BOOK, "give_up": GIVE_UP}
