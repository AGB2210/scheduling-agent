"""A local web page for trying the agent on one typed request."""

import json
import random
import threading
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from schedagent.agent import LLM, Trace, run_agent
from schedagent.generator import make_task
from schedagent.slots import DAY_NAMES, SLOTS_PER_DAY, Block, slot_to_time
from schedagent.tools import Session
from schedagent.versions import VERSIONS, Version

PAGE = Path(__file__).parent / "static" / "index.html"
ADDRESS = "127.0.0.1"  # reachable from this computer only
# The page offers weeks 0 to 999. The practice and test sets start at seed
# 1000, so nothing tried on the page is ever one of their tasks.
WEEKS = 1000
MAX_REQUEST_CHARS = 500
MAX_BODY_BYTES = 10_000


class WeekArgs(BaseModel, extra="forbid"):
    seed: int = Field(ge=0, lt=WEEKS)


class ScheduleArgs(WeekArgs):
    request: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_REQUEST_CHARS
        ),
    ]
    agent: str = "solver"

    @field_validator("agent")
    @classmethod
    def _known_agent(cls, name: str) -> str:
        if name not in VERSIONS:
            raise ValueError(f"must be one of {', '.join(sorted(VERSIONS))}")
        return name


def week_view(seed: int) -> dict:
    """One generated week, in the form the page draws it."""
    task = make_task(seed)
    return {
        "seed": seed,
        "days": DAY_NAMES,
        # One more time than there are slots: the last is when the day ends.
        "times": [slot_to_time(slot) for slot in range(SLOTS_PER_DAY + 1)],
        "people": [
            {
                "name": person,
                "busy": [_block_view(block) for block in task.calendar.busy(person)],
            }
            for person in task.calendar.people
        ],
        "example": task.request,
    }


def schedule(
    args: ScheduleArgs, llm_for: Callable[[Version], LLM], max_turns: int = 12
) -> dict:
    """Run the agent on one typed request and describe what it did."""
    version = VERSIONS[args.agent]
    session = Session(make_task(args.seed).calendar, version.tools)
    started = time.perf_counter()
    trace = run_agent(
        args.request,
        session,
        llm_for(version),
        max_turns,
        system_prompt=version.system_prompt,
    )
    seconds = time.perf_counter() - started
    return {
        "outcome": trace.outcome,
        "booking": _booking_view(session),
        "reason": next(
            (step.args.get("reason") for step in trace.steps if step.tool == "give_up"),
            None,
        ),
        "events": _events(trace),
        "llm_calls": trace.llm_calls,
        "max_turns": max_turns,
        "seconds": round(seconds, 2),
    }


def _block_view(block: Block) -> dict:
    return {"day": block.day, "start": block.start, "length": block.length}


def _booking_view(session: Session) -> dict | None:
    booking = session.booking
    if booking is None:
        return None
    attendees = sorted(booking.attendees)
    return {
        **_block_view(booking.block),
        "attendees": attendees,
        # A typed request has no list of rules to grade against. What can
        # still be checked is whether anyone booked is busy at that time.
        "busy": [
            person
            for person in attendees
            if not session.calendar.is_free(person, booking.block)
        ],
    }


def _events(trace: Trace) -> list[dict]:
    """What the model wrote and which tools it called, in order."""
    steps = iter(trace.steps)
    events = []
    # The first two messages are the instructions and the request.
    for message in trace.messages[2:]:
        if message["role"] == "assistant" and message["content"].strip():
            events.append({"kind": "said", "text": message["content"].strip()})
        elif message["role"] == "tool":
            step = next(steps)
            events.append(
                {
                    "kind": "tool",
                    "tool": step.tool,
                    "args": step.args,
                    "result": step.result,
                }
            )
    return events


def _problems(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )


def make_server(
    llm_for: Callable[[Version], LLM], port: int = 8000
) -> ThreadingHTTPServer:
    """Build the web server. `llm_for` gives the model for an agent version."""
    page = PAGE.read_bytes()
    one_at_a_time = threading.Lock()  # the model works on one request at a time

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif url.path == "/api/week":
                self._week(parse_qs(url.query).get("seed"))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/schedule":
                return self._json(404, {"error": "not found"})
            # A page on some other website cannot send JSON here without the
            # browser asking this server first, and that question is never
            # answered. So only our own page can start the model.
            if self.headers.get_content_type() != "application/json":
                return self._json(415, {"error": "send the request as JSON"})
            length = self.headers.get("Content-Length", "")
            if not length.isdigit():
                return self._json(400, {"error": "Content-Length is missing"})
            if int(length) > MAX_BODY_BYTES:
                return self._json(413, {"error": "the request is too large"})
            try:
                args = ScheduleArgs.model_validate_json(self.rfile.read(int(length)))
            except ValidationError as error:
                return self._json(400, {"error": _problems(error)})
            try:
                with one_at_a_time:
                    result = schedule(args, llm_for)
            except Exception as error:
                # Whatever stopped the model, the page should be told, and
                # the server should stay up for the next request.
                return self._json(500, {"error": f"the model could not run: {error}"})
            self._json(200, result)

        def _week(self, seed: list[str] | None) -> None:
            if seed is None:
                return self._json(200, week_view(random.randrange(WEEKS)))
            try:
                args = WeekArgs.model_validate({"seed": seed[0]})
            except ValidationError as error:
                return self._json(400, {"error": _problems(error)})
            self._json(200, week_view(args.seed))

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            pass  # do not print a line for every request

    return ThreadingHTTPServer((ADDRESS, port), Handler)


def serve(
    llm_for: Callable[[Version], LLM], port: int = 8000, open_browser: bool = True
) -> None:
    """Serve the page until Ctrl+C is pressed."""
    try:
        server = make_server(llm_for, port)
    except OSError as error:
        raise SystemExit(
            f"Could not use port {port}: {error}. Try another one with --port."
        ) from None
    url = f"http://{ADDRESS}:{port}"
    print(f"The page is at {url}. Press Ctrl+C here to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
