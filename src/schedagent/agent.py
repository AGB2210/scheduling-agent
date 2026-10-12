"""The agent loop: ask the model, run the tools it asks for, repeat."""

from collections.abc import Callable
from dataclasses import dataclass

from schedagent.tools import Session

SYSTEM_PROMPT = """\
You schedule one meeting for the people named in the request.
The week runs Monday to Friday, 09:00 to 17:00. Meetings start and end on the \
hour or half hour.
Use the tools to look at calendars before you decide. Never guess when someone \
is free.
Rules stated firmly in the request must be followed. Wishes such as "ideally" \
or "if possible" should be followed when some time allows it, and dropped when \
none does.
When you have found a time, call book once. If no time can follow the firm \
rules, call give_up.
"""

NUDGE = "Reply by calling one of the tools."


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict


@dataclass(frozen=True)
class Reply:
    """What the model said: some text, some tool calls, or both."""

    text: str = ""
    calls: tuple[ToolCall, ...] = ()


# A model is anything that reads the conversation so far and gives a Reply.
LLM = Callable[[list[dict]], Reply]


@dataclass(frozen=True)
class Step:
    """One tool call and what came back."""

    tool: str
    args: dict
    result: str


@dataclass(frozen=True)
class Trace:
    """Everything that happened in one run."""

    steps: tuple[Step, ...]
    messages: tuple[dict, ...]
    llm_calls: int
    outcome: str  # "booked", "gave_up" or "out_of_turns"


def run_agent(request: str, session: Session, llm: LLM, max_turns: int = 12) -> Trace:
    """Let the model work on one request until it books, gives up, or runs out."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request},
    ]
    steps = []
    llm_calls = 0
    while llm_calls < max_turns and not session.finished:
        reply = llm(messages)
        llm_calls += 1
        messages.append(
            {
                "role": "assistant",
                "content": reply.text,
                "tool_calls": [
                    {"name": call.name, "args": call.args} for call in reply.calls
                ],
            }
        )
        if not reply.calls:
            messages.append({"role": "user", "content": NUDGE})
        for call in reply.calls:
            result = session.call(call.name, call.args)
            steps.append(Step(tool=call.name, args=call.args, result=result))
            messages.append({"role": "tool", "name": call.name, "content": result})
            if session.finished:
                break
    return Trace(
        steps=tuple(steps),
        messages=tuple(messages),
        llm_calls=llm_calls,
        outcome=_outcome(session),
    )


def _outcome(session: Session) -> str:
    if session.booking is not None:
        return "booked"
    if session.gave_up:
        return "gave_up"
    return "out_of_turns"
