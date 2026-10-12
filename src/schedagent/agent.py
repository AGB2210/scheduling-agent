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

# For the agent that has find_slots in place of get_busy.
SOLVER_PROMPT = """\
You schedule one meeting for the people named in the request.
The week runs Monday to Friday, 09:00 to 17:00. Meetings start and end on the \
hour or half hour.
Call find_slots to get the times when everyone is free. Give it every firm rule \
in the request: who must attend, how long the meeting is, and any limit on the \
days or the hours.
If the request rules days out, list those days in excluded_days. If it names \
the only days that work, list those days in days.
Wishes such as "ideally" or "if possible" are not firm rules. To follow one, \
first call find_slots with the wish included. If that finds nothing, call it \
again without the wish.
Then call book with one of the slots that find_slots returned. If find_slots \
finds no slot for the firm rules, call give_up.

Examples of turning a request into find_slots arguments:

Request: Asha and Vikram need 30 minutes together. Thursday doesn't suit them. \
They have to be done by 15:00.
Arguments: {"attendees": ["Asha", "Vikram"], "duration_minutes": 30, \
"excluded_days": ["Thursday"], "latest_end": "15:00"}

Request: Get Leela, Imran and Sana together for 2 hours, on Tuesday or \
Wednesday only. After 10:00 would be nice.
Arguments, with the wish: {"attendees": ["Leela", "Imran", "Sana"], \
"duration_minutes": 120, "days": ["Tuesday", "Wednesday"], \
"earliest_start": "10:00"}
Arguments, if that finds nothing: {"attendees": ["Leela", "Imran", "Sana"], \
"duration_minutes": 120, "days": ["Tuesday", "Wednesday"]}

Request: Vikram and Sana should meet for an hour, avoiding Monday and Friday. \
Wednesday is their first choice.
Arguments, with the wish: {"attendees": ["Vikram", "Sana"], \
"duration_minutes": 60, "days": ["Wednesday"]}
Arguments, if that finds nothing: {"attendees": ["Vikram", "Sana"], \
"duration_minutes": 60, "excluded_days": ["Monday", "Friday"]}

Example of booking. If find_slots returns:
{"count": 2, "slots": [{"day": "Tuesday", "start": "10:00", "end": "10:30"}, \
{"day": "Thursday", "start": "14:30", "end": "15:00"}]}
then book one of those slots, copying its day, start and end together:
{"attendees": ["Asha", "Vikram"], "day": "Thursday", "start": "14:30", \
"end": "15:00"}
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


def run_agent(
    request: str,
    session: Session,
    llm: LLM,
    max_turns: int = 12,
    system_prompt: str = SYSTEM_PROMPT,
) -> Trace:
    """Let the model work on one request until it books, gives up, or runs out."""
    messages = [
        {"role": "system", "content": system_prompt},
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
