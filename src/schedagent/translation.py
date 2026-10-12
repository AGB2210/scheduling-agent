"""Compare the rules the model gave find_slots with a task's true rules."""

from pydantic import ValidationError

from schedagent.rules import MeetingRules
from schedagent.tools import FindSlotsArgs, ToolError, rules_from_search

FIELDS = ["attendees", "length", "days", "hours"]


def last_search(record: dict) -> MeetingRules | None:
    """The rules in the last find_slots call the tool accepted, if any."""
    for step in reversed(record["steps"]):
        if step["tool"] == "find_slots" and not step["result"].startswith("Error:"):
            try:
                return rules_from_search(FindSlotsArgs.model_validate(step["args"]))
            except (ValidationError, ToolError):
                return None
    return None


def compare(searched: MeetingRules, true: MeetingRules) -> dict[str, str]:
    """Judge each rule in a search as exact, narrower or wrong.

    Narrower means the search left out times the true rules allow, which is
    what including a wish does. Wrong means it let in something the true rules
    forbid, or named the wrong people or length.
    """
    days = _width(
        searched.must.days == true.must.days, searched.must.days <= true.must.days
    )
    hours = _width(
        (searched.must.earliest, searched.must.latest)
        == (true.must.earliest, true.must.latest),
        searched.must.earliest >= true.must.earliest
        and searched.must.latest <= true.must.latest,
    )
    return {
        "attendees": "exact" if searched.attendees == true.attendees else "wrong",
        "length": "exact" if searched.length == true.length else "wrong",
        "days": days,
        "hours": hours,
    }


def _width(same: bool, inside: bool) -> str:
    if same:
        return "exact"
    return "narrower" if inside else "wrong"
