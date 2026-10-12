"""The tools the agent can call. They are its only view of the calendars."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from schedagent.calendar import Calendar
from schedagent.rules import Booking
from schedagent.slots import DAY_NAMES, DAYS, Block, slot_to_time, time_to_slot


class ToolError(Exception):
    """A mistake in a tool call that the agent should be told about."""


class GetBusyArgs(BaseModel, extra="forbid"):
    person: str


class BookArgs(BaseModel, extra="forbid"):
    attendees: list[str] = Field(min_length=1)
    day: str
    start: str
    end: str


class GiveUpArgs(BaseModel, extra="forbid"):
    reason: str


class Session:
    """One task's calendars, plus whatever the agent ends up deciding."""

    def __init__(self, calendar: Calendar):
        self.calendar = calendar
        self.booking: Booking | None = None
        self.gave_up = False

    @property
    def finished(self) -> bool:
        return self.booking is not None or self.gave_up

    def call(self, name: str, args: dict) -> str:
        """Run one tool call. A mistake comes back as an error message."""
        if self.finished:
            return "Error: this task is already finished."
        if name not in TOOLS:
            return f"Error: there is no tool called {name!r}."
        tool = TOOLS[name]
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
TOOLS = {
    "get_busy": Tool(
        "Show when one person is busy this week.", GetBusyArgs, Session._get_busy
    ),
    "book": Tool(
        "Book the meeting. Times look like 14:00 and fall on the hour or half "
        "hour, between 09:00 and 17:00. This ends the task.",
        BookArgs,
        Session._book,
    ),
    "give_up": Tool(
        "Say that no time works for this meeting. This ends the task.",
        GiveUpArgs,
        Session._give_up,
    ),
}
