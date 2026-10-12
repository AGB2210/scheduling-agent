import pytest

from schedagent.agent import NUDGE, SYSTEM_PROMPT, Reply, Step, ToolCall, run_agent
from schedagent.calendar import Calendar
from schedagent.rules import Booking
from schedagent.slots import Block
from schedagent.tools import Session

MON, TUE = 0, 1
REQUEST = "Ravi and Meera need to meet for 1 hour. Not on Monday."


class Script:
    """A fake model that plays back replies written in advance."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []  # the conversation as it stood at each call

    def __call__(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def call(name, **args):
    return Reply(calls=(ToolCall(name=name, args=args),))


def book(day="Tuesday", start="10:00", end="11:00"):
    return call("book", attendees=["Ravi", "Meera"], day=day, start=start, end=end)


@pytest.fixture
def session():
    return Session(
        Calendar(
            {
                "Ravi": [Block(day=TUE, start=0, length=2)],  # Tue 9:00-10:00
                "Meera": [],
            }
        )
    )


def test_model_looks_at_calendars_then_books(session):
    model = Script(
        call("get_busy", person="Ravi"),
        call("get_busy", person="Meera"),
        book(),
    )
    trace = run_agent(REQUEST, session, model)

    assert trace.outcome == "booked"
    assert trace.llm_calls == 3
    assert [step.tool for step in trace.steps] == ["get_busy", "get_busy", "book"]
    assert session.booking == Booking(
        attendees={"Ravi", "Meera"}, block=Block(day=TUE, start=2, length=2)
    )


def test_conversation_starts_with_the_instructions_and_the_request(session):
    model = Script(book())
    run_agent(REQUEST, session, model)
    assert model.seen[0] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": REQUEST},
    ]


def test_model_is_shown_each_tool_result(session):
    model = Script(call("get_busy", person="Ravi"), book())
    run_agent(REQUEST, session, model)
    assert model.seen[1][-2:] == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "get_busy", "args": {"person": "Ravi"}}],
        },
        {
            "role": "tool",
            "name": "get_busy",
            "content": '[{"day": "Tuesday", "start": "09:00", "end": "10:00"}]',
        },
    ]


def test_model_can_recover_from_an_error(session):
    model = Script(call("get_busy", person="Zoya"), book())
    trace = run_agent(REQUEST, session, model)
    assert trace.steps[0] == Step(
        tool="get_busy", args={"person": "Zoya"}, result="Error: unknown person: Zoya"
    )
    assert model.seen[1][-1]["content"] == "Error: unknown person: Zoya"
    assert trace.outcome == "booked"


def test_give_up_ends_the_run(session):
    model = Script(call("give_up", reason="no time works"))
    trace = run_agent(REQUEST, session, model)
    assert trace.outcome == "gave_up"
    assert session.booking is None


def test_model_that_only_talks_is_nudged_to_use_a_tool(session):
    model = Script(Reply(text="Tuesday at 10:00 looks good."), book())
    trace = run_agent(REQUEST, session, model)
    assert model.seen[1][-1] == {"role": "user", "content": NUDGE}
    assert trace.llm_calls == 2
    assert trace.outcome == "booked"


def test_run_stops_when_the_turns_run_out(session):
    model = Script(*[call("get_busy", person="Ravi")] * 10)
    trace = run_agent(REQUEST, session, model, max_turns=3)
    assert trace.outcome == "out_of_turns"
    assert trace.llm_calls == 3
    assert len(trace.steps) == 3
    assert not session.finished


def test_several_calls_in_one_reply_run_in_order(session):
    both = Reply(
        calls=(
            ToolCall("get_busy", {"person": "Ravi"}),
            ToolCall("get_busy", {"person": "Meera"}),
        )
    )
    trace = run_agent(REQUEST, session, Script(both, book()))
    assert [step.args for step in trace.steps[:2]] == [
        {"person": "Ravi"},
        {"person": "Meera"},
    ]
    assert trace.llm_calls == 2


def test_calls_after_the_booking_are_not_run(session):
    book_then_more = Reply(
        calls=(book().calls[0], ToolCall("get_busy", {"person": "Ravi"}))
    )
    trace = run_agent(REQUEST, session, Script(book_then_more))
    assert [step.tool for step in trace.steps] == ["book"]


def test_model_is_not_asked_again_after_the_task_is_finished(session):
    model = Script(book(), book(day="Monday"))
    run_agent(REQUEST, session, model)
    assert len(model.replies) == 1
