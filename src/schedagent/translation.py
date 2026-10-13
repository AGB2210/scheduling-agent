"""Compare the rules the model gave find_slots with a task's true rules."""

from pydantic import ValidationError

from schedagent.rules import MeetingRules
from schedagent.tools import FindSlotsWishArgs, ToolError, rules_from_search

FIELDS = ["attendees", "length", "days", "hours"]


def last_search(record: dict) -> MeetingRules | None:
    """The rules in the last find_slots call the tool accepted, if any.

    A wish stated apart from the firm rules comes back as the rules' `prefer`.
    """
    for step in reversed(record["steps"]):
        if step["tool"] == "find_slots" and not step["result"].startswith("Error:"):
            try:
                # This reads both agents' searches: the second solver agent's
                # arguments are the first one's plus the wishes.
                args = FindSlotsWishArgs.model_validate(step["args"])
                return rules_from_search(args)
            except (ValidationError, ToolError):
                return None
    return None


def compare_wish(searched: MeetingRules, true: MeetingRules) -> str:
    """Judge the wish in a search: exact, missing, or wrong.

    Exact also covers a task with no wish searched with none. Missing means
    the task has a wish and the search states none. Wrong is anything else: a
    different wish, or a wish where the task has none.
    """
    if searched.prefer == true.prefer:
        return "exact"
    return "missing" if searched.prefer is None else "wrong"


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
