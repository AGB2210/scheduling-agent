"""Grade a finished run against the task's hidden rules."""

from dataclasses import dataclass

from schedagent.generator import Task
from schedagent.rules import check
from schedagent.solver import preferred_blocks, valid_blocks
from schedagent.tools import Session


@dataclass(frozen=True)
class Grade:
    """The verdict on one run."""

    kind: str  # "correct", "bad_booking", "gave_up_wrongly" or "no_answer"
    problems: tuple[str, ...] = ()  # the hard rules a bad booking broke
    kept_preference: bool | None = None  # None when there was none to keep

    @property
    def correct(self) -> bool:
        return self.kind == "correct"


def grade(task: Task, session: Session) -> Grade:
    possible = bool(valid_blocks(task.rules, task.calendar))
    if session.booking is None:
        if not session.gave_up:
            return Grade("no_answer")
        return Grade("gave_up_wrongly" if possible else "correct")
    verdict = check(task.rules, task.calendar, session.booking)
    if not verdict.valid:
        return Grade("bad_booking", problems=verdict.problems)
    # A preference only counts when some valid slot could have kept it.
    kept = None
    if task.rules.prefer is not None and preferred_blocks(task.rules, task.calendar):
        kept = verdict.keeps_preference
    return Grade("correct", kept_preference=kept)
