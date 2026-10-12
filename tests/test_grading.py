import pytest

from schedagent.agent import Reply, ToolCall, run_agent
from schedagent.calendar import Calendar
from schedagent.generator import Task, make_task
from schedagent.grading import Grade, grade
from schedagent.rules import MeetingRules, Window
from schedagent.slots import DAY_NAMES, Block, slot_to_time
from schedagent.solver import valid_blocks
from schedagent.tools import Session

MON, TUE, WED = 0, 1, 2


def make(busy, **rules):
    calendar = Calendar(busy)
    return Task(seed=0, calendar=calendar, rules=MeetingRules(**rules), request="")


def booked(task, day, start, end, attendees=("Ravi", "Meera")):
    session = Session(task.calendar)
    reply = session.call(
        "book", {"attendees": list(attendees), "day": day, "start": start, "end": end}
    )
    assert reply == "Booked."
    return session


def gave_up(task):
    session = Session(task.calendar)
    session.call("give_up", {"reason": "no time works"})
    return session


@pytest.fixture
def task():
    # 30 minutes with Ravi and Meera on Monday, mornings preferred.
    return make(
        {"Ravi": [Block(day=MON, start=0, length=2)], "Meera": []},  # Mon 9:00-10:00
        attendees={"Ravi", "Meera"},
        length=1,
        must=Window(days={MON}),
        prefer=Window(latest=6),
    )


@pytest.fixture
def impossible_task():
    return make(
        {"Ravi": [Block(day=MON, start=0, length=16)], "Meera": []},
        attendees={"Ravi", "Meera"},
        length=1,
        must=Window(days={MON}),
    )


def test_valid_booking_that_keeps_the_preference(task):
    result = grade(task, booked(task, "Monday", "10:00", "10:30"))
    assert result == Grade("correct", kept_preference=True)
    assert result.correct


def test_valid_booking_that_misses_a_preference_it_could_have_kept(task):
    result = grade(task, booked(task, "Monday", "14:00", "14:30"))
    assert result == Grade("correct", kept_preference=False)


def test_preference_nobody_could_keep_is_not_counted():
    task = make(
        {"Ravi": [Block(day=MON, start=0, length=6)], "Meera": []},  # Mon 9:00-12:00
        attendees={"Ravi", "Meera"},
        length=1,
        must=Window(days={MON}),
        prefer=Window(latest=6),
    )
    result = grade(task, booked(task, "Monday", "14:00", "14:30"))
    assert result == Grade("correct", kept_preference=None)


def test_no_preference_is_not_counted():
    task = make({"Ravi": [], "Meera": []}, attendees={"Ravi", "Meera"}, length=1)
    result = grade(task, booked(task, "Monday", "14:00", "14:30"))
    assert result == Grade("correct", kept_preference=None)


def test_bad_booking_lists_the_broken_rules(task):
    result = grade(task, booked(task, "Tuesday", "09:30", "10:30"))
    assert result == Grade("bad_booking", problems=("wrong length", "day not allowed"))
    assert not result.correct


def test_booking_while_someone_is_busy_is_a_bad_booking(task):
    result = grade(task, booked(task, "Monday", "09:30", "10:00"))
    assert result == Grade("bad_booking", problems=("Ravi is busy",))


def test_giving_up_when_a_slot_existed_is_wrong(task):
    assert grade(task, gave_up(task)) == Grade("gave_up_wrongly")


def test_giving_up_on_an_impossible_task_is_correct(impossible_task):
    assert grade(impossible_task, gave_up(impossible_task)).correct


def test_booking_on_an_impossible_task_is_a_bad_booking(impossible_task):
    session = booked(impossible_task, "Monday", "10:00", "10:30")
    assert grade(impossible_task, session) == Grade(
        "bad_booking", problems=("Ravi is busy",)
    )


def test_run_that_never_answered(task, impossible_task):
    assert grade(task, Session(task.calendar)) == Grade("no_answer")
    assert grade(impossible_task, Session(impossible_task.calendar)) == Grade(
        "no_answer"
    )


@pytest.mark.parametrize("seed", range(200))
def test_a_model_that_copies_the_solver_is_always_graded_correct(seed):
    """Runs the whole pipeline: generator, tools, loop, and grader."""
    task = make_task(seed)
    valid = valid_blocks(task.rules, task.calendar)
    if valid:
        block = valid[0]
        answer = ToolCall(
            "book",
            {
                "attendees": sorted(task.rules.attendees),
                "day": DAY_NAMES[block.day],
                "start": slot_to_time(block.start),
                "end": slot_to_time(block.end),
            },
        )
    else:
        answer = ToolCall("give_up", {"reason": "no time works"})
    session = Session(task.calendar)
    run_agent(task.request, session, lambda messages: Reply(calls=(answer,)))
    assert grade(task, session).correct
