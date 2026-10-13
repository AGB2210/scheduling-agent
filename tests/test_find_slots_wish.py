import json

import pytest

from schedagent.agent import Reply, ToolCall, run_agent
from schedagent.calendar import Calendar
from schedagent.generator import make_task
from schedagent.grading import grade
from schedagent.rules import ALL_DAYS
from schedagent.slots import DAY_NAMES, SLOT_MINUTES, SLOTS_PER_DAY, Block, slot_to_time
from schedagent.tools import SOLVER2_TOOLS, SOLVER_TOOLS, Session
from schedagent.versions import SOLVER2

MON, TUE = 0, 1
BOTH = ["Ravi", "Meera"]


@pytest.fixture
def session():
    calendar = Calendar(
        {
            "Ravi": [Block(day=MON, start=0, length=8)],  # Mon 9:00-13:00
            "Meera": [Block(day=TUE, start=8, length=8)],  # Tue 13:00-17:00
        }
    )
    return Session(calendar, SOLVER2_TOOLS)


def find(session, **changes):
    # All day on Monday or Tuesday: only Mon 13:00-17:00 and Tue 9:00-13:00 fit.
    args = {
        "attendees": BOTH,
        "duration_minutes": 240,
        "days": ["Monday", "Tuesday"],
        **changes,
    }
    return json.loads(session.call("find_slots", args))


MONDAY = {"day": "Monday", "start": "13:00", "end": "17:00"}
TUESDAY = {"day": "Tuesday", "start": "09:00", "end": "13:00"}


def test_without_a_wish_it_is_the_same_search_as_before(session):
    assert find(session) == {"count": 2, "slots": [MONDAY, TUESDAY]}


def test_a_wish_that_some_slot_keeps_leaves_only_those_slots(session):
    assert find(session, preferred_days=["Tuesday"]) == {
        "count": 1,
        "wish_kept": True,
        "slots": [TUESDAY],
    }
    assert find(session, preferred_earliest_start="13:00") == {
        "count": 1,
        "wish_kept": True,
        "slots": [MONDAY],
    }
    assert find(session, preferred_latest_end="13:00") == {
        "count": 1,
        "wish_kept": True,
        "slots": [TUESDAY],
    }


def test_a_wish_that_no_slot_keeps_is_dropped(session):
    assert find(session, preferred_days=["Wednesday"]) == {
        "count": 2,
        "wish_kept": False,
        "slots": [MONDAY, TUESDAY],
    }
    # Each part of this wish can be kept, but not both together.
    both_parts = find(
        session, preferred_days=["Tuesday"], preferred_earliest_start="13:00"
    )
    assert both_parts["wish_kept"] is False
    assert both_parts["count"] == 2


def test_a_wish_never_adds_a_slot_the_firm_rules_forbid(session):
    result = find(session, days=["Monday"], preferred_days=["Tuesday"])
    assert result == {"count": 1, "wish_kept": False, "slots": [MONDAY]}


def test_when_the_firm_rules_find_nothing_a_wish_changes_nothing(session):
    result = find(session, days=["Monday"], latest_end="13:00", preferred_days=["Monday"])
    assert result == {"count": 0, "slots": []}


def test_an_empty_list_of_preferred_days_is_no_wish(session):
    assert find(session, preferred_days=[]) == {"count": 2, "slots": [MONDAY, TUESDAY]}


def test_only_the_slots_that_were_returned_can_be_booked(session):
    find(session, preferred_days=["Tuesday"])
    refused = session.call("book", {"attendees": BOTH, **MONDAY})
    assert refused.startswith("Error: that is not a slot")
    assert session.call("book", {"attendees": BOTH, **TUESDAY}) == "Booked."


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"preferred_days": ["Sunday"]}, "'Sunday' is not a day from Monday to Friday"),
        ({"preferred_days": "Monday"}, "preferred_days: Input should be a valid list"),
        ({"preferred_earliest_start": "noon"}, "'noon' is not a time"),
        (
            {"preferred_earliest_start": "14:00", "preferred_latest_end": "12:00"},
            "preferred_latest_end must be after preferred_earliest_start",
        ),
        ({"preferred_earliest_start": "17:00"}, "preferred_latest_end must be after"),
        ({"preferred_latest_end": "09:00"}, "preferred_latest_end must be after"),
        ({"wish": "Tuesday"}, "wish: Extra inputs are not permitted"),
    ],
)
def test_a_badly_stated_wish_is_an_error(session, changes, message):
    reply = session.call(
        "find_slots", {"attendees": BOTH, "duration_minutes": 60, **changes}
    )
    assert reply.startswith("Error: ")
    assert message in reply
    assert session.found is None


def test_the_first_solver_agent_cannot_state_a_wish():
    first = Session(Calendar({"Ravi": [], "Meera": []}), SOLVER_TOOLS)
    reply = first.call(
        "find_slots",
        {"attendees": BOTH, "duration_minutes": 60, "preferred_days": ["Monday"]},
    )
    assert reply == "Error: preferred_days: Extra inputs are not permitted"


def test_the_description_explains_each_argument():
    properties = SOLVER2_TOOLS["find_slots"].args.model_json_schema()["properties"]
    assert set(properties) == {
        "attendees",
        "duration_minutes",
        "days",
        "excluded_days",
        "earliest_start",
        "latest_end",
        "preferred_days",
        "preferred_earliest_start",
        "preferred_latest_end",
    }
    assert all(field.get("description") for field in properties.values())


def true_rules_as_arguments(task):
    """The arguments a model would give if it read the request perfectly."""
    must, prefer = task.rules.must, task.rules.prefer
    args = {
        "attendees": sorted(task.rules.attendees),
        "duration_minutes": task.rules.length * SLOT_MINUTES,
        "days": [DAY_NAMES[day] for day in sorted(must.days)],
        "earliest_start": slot_to_time(must.earliest),
        "latest_end": slot_to_time(must.latest),
    }
    if prefer is not None:
        if prefer.days != ALL_DAYS:
            args["preferred_days"] = [DAY_NAMES[day] for day in sorted(prefer.days)]
        if prefer.earliest > 0:
            args["preferred_earliest_start"] = slot_to_time(prefer.earliest)
        if prefer.latest < SLOTS_PER_DAY:
            args["preferred_latest_end"] = slot_to_time(prefer.latest)
    return args


@pytest.mark.parametrize("seed", range(200))
def test_a_model_that_states_rules_and_wish_correctly_needs_one_search(seed):
    """A fake model that searches once, then books the first slot or gives up."""
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

    session = Session(task.calendar, SOLVER2.tools)
    trace = run_agent(task.request, session, model, system_prompt=SOLVER2.system_prompt)
    result = grade(task, session)
    assert trace.llm_calls == 2
    assert result.correct
    # The wish is kept whenever some valid slot allows it.
    assert result.kept_preference is not False
