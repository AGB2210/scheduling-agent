import json

import pytest

from schedagent.agent import Reply, ToolCall, run_agent
from schedagent.calendar import Calendar
from schedagent.generator import make_task
from schedagent.grading import grade
from schedagent.slots import DAY_NAMES, SLOT_MINUTES, Block, slot_to_time
from schedagent.solver import valid_blocks
from schedagent.tools import MAX_SLOTS_SHOWN, SOLVER_TOOLS, Session

MON, TUE = 0, 1


@pytest.fixture
def session():
    calendar = Calendar(
        {
            "Ravi": [Block(day=MON, start=0, length=2)],  # Mon 9:00-10:00
            "Meera": [Block(day=MON, start=4, length=1)],  # Mon 11:00-11:30
        }
    )
    return Session(calendar, SOLVER_TOOLS)


def find(session, **changes):
    args = {"attendees": ["Ravi", "Meera"], "duration_minutes": 60, **changes}
    return json.loads(session.call("find_slots", args))


def test_finds_the_only_slot_that_fits(session):
    result = find(session, days=["Monday"], latest_end="12:00")
    assert result == {
        "count": 1,
        "slots": [{"day": "Monday", "start": "10:00", "end": "11:00"}],
    }
    assert not session.finished


def test_no_slot_gives_a_count_of_zero(session):
    result = find(session, days=["Monday"], earliest_start="09:00", latest_end="10:00")
    assert result == {"count": 0, "slots": []}


def test_leaving_out_days_and_hours_allows_the_whole_week(session):
    result = find(session, attendees=["Meera"], duration_minutes=30)
    assert result["count"] == 79  # 80 half hours, less the one Meera is busy
    assert len(result["slots"]) == MAX_SLOTS_SHOWN
    assert result["slots"][0] == {"day": "Monday", "start": "09:00", "end": "09:30"}


def test_days_limit_the_search(session):
    result = find(session, days=["Tue", "wednesday"], duration_minutes=480)
    assert result == {
        "count": 2,
        "slots": [
            {"day": "Tuesday", "start": "09:00", "end": "17:00"},
            {"day": "Wednesday", "start": "09:00", "end": "17:00"},
        ],
    }


def test_earliest_start_limits_the_search(session):
    result = find(session, days=["Monday"], earliest_start="16:00")
    assert result["slots"] == [{"day": "Monday", "start": "16:00", "end": "17:00"}]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"attendees": ["Ravi", "Zoya"]}, "unknown person: Zoya"),
        ({"duration_minutes": 45}, "duration_minutes must be a multiple of 30"),
        ({"duration_minutes": 0}, "duration_minutes must be a multiple of 30"),
        ({"duration_minutes": 510}, "duration_minutes must be a multiple of 30"),
        ({"days": ["Saturday"]}, "'Saturday' is not a day from Monday to Friday"),
        ({"days": []}, "days must name at least one day"),
        ({"days": "Monday"}, "days: Input should be a valid list"),
        ({"earliest_start": "13:15"}, "'13:15' is not a time between 09:00 and 17:00"),
        (
            {"earliest_start": "14:00", "latest_end": "12:00"},
            "latest_end must be after earliest_start",
        ),
        ({"length": 60}, "length: Extra inputs are not permitted"),
        ({"attendees": []}, "attendees: List should have at least 1 item"),
    ],
)
def test_a_bad_search_is_an_error(session, changes, message):
    args = {"attendees": ["Ravi", "Meera"], "duration_minutes": 60, **changes}
    reply = session.call("find_slots", args)
    assert reply.startswith("Error: ")
    assert message in reply


def test_the_description_explains_each_argument():
    properties = SOLVER_TOOLS["find_slots"].args.model_json_schema()["properties"]
    assert set(properties) == {
        "attendees",
        "duration_minutes",
        "days",
        "earliest_start",
        "latest_end",
    }
    assert all(field.get("description") for field in properties.values())


def true_rules_as_arguments(task):
    """The arguments a model would give if it read the request perfectly."""
    must = task.rules.must
    return {
        "attendees": sorted(task.rules.attendees),
        "duration_minutes": task.rules.length * SLOT_MINUTES,
        "days": [DAY_NAMES[day] for day in sorted(must.days)],
        "earliest_start": slot_to_time(must.earliest),
        "latest_end": slot_to_time(must.latest),
    }


@pytest.mark.parametrize("seed", range(200))
def test_given_the_true_rules_the_tool_agrees_with_the_solver(seed):
    task = make_task(seed)
    session = Session(task.calendar, SOLVER_TOOLS)
    result = json.loads(session.call("find_slots", true_rules_as_arguments(task)))
    valid = valid_blocks(task.rules, task.calendar)
    assert result["count"] == len(valid)
    assert result["slots"] == [
        {
            "day": DAY_NAMES[block.day],
            "start": slot_to_time(block.start),
            "end": slot_to_time(block.end),
        }
        for block in valid[:MAX_SLOTS_SHOWN]
    ]


@pytest.mark.parametrize("seed", range(200))
def test_a_model_that_states_the_rules_correctly_is_graded_correct(seed):
    """A fake model that searches with the true rules, then books or gives up."""
    task = make_task(seed)
    attendees = sorted(task.rules.attendees)

    def model(messages):
        last = messages[-1]
        if last["role"] != "tool":
            return Reply(
                calls=(ToolCall("find_slots", true_rules_as_arguments(task)),)
            )
        found = json.loads(last["content"])
        if not found["slots"]:
            return Reply(calls=(ToolCall("give_up", {"reason": "no slot fits"}),))
        return Reply(
            calls=(ToolCall("book", {"attendees": attendees, **found["slots"][0]}),)
        )

    session = Session(task.calendar, SOLVER_TOOLS)
    trace = run_agent(task.request, session, model)
    assert trace.llm_calls == 2
    assert grade(task, session).correct
