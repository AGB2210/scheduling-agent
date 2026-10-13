import json
import threading
import urllib.error
import urllib.request

import pytest
from pydantic import ValidationError

from schedagent.agent import Reply, ToolCall
from schedagent.generator import make_task
from schedagent.rules import MeetingRules
from schedagent.sets import HELD_OUT_START, PRACTICE_START
from schedagent.slots import DAY_NAMES, slot_to_time
from schedagent.solver import valid_blocks
from schedagent.versions import PLAIN, SOLVER
from schedagent.web import (
    MAX_BODY_BYTES,
    MAX_NAME_CHARS,
    MAX_PEOPLE,
    MAX_REQUEST_CHARS,
    WEEKS,
    ScheduleArgs,
    make_server,
    schedule,
    week_view,
)

SEED = 7
CALENDAR = make_task(SEED).calendar
# Someone with something in their week, a time they are busy, and one they are free.
PERSON = next(person for person in CALENDAR.people if CALENDAR.busy(person))
BUSY = CALENDAR.busy(PERSON)[0]
FREE = valid_blocks(MeetingRules(attendees=[PERSON], length=1), CALENDAR)[0]


class Script:
    """A fake model that plays back replies written in advance."""

    def __init__(self, *replies):
        self.replies = list(replies)

    def __call__(self, messages):
        return self.replies.pop(0)


def call(name, **args):
    return Reply(calls=(ToolCall(name=name, args=args),))


def book(block):
    return call(
        "book",
        attendees=[PERSON],
        day=DAY_NAMES[block.day],
        start=slot_to_time(block.start),
        end=slot_to_time(block.end),
    )


def scripted(*replies):
    """The same script for whichever agent version is asked for."""
    return lambda version: Script(*replies)


def args(**changes):
    return ScheduleArgs(**{"seed": SEED, "request": "Find a time.", **changes})


def test_week_view_lists_each_person_and_when_they_are_busy():
    view = week_view(SEED)
    assert view["seed"] == SEED
    assert view["days"] == DAY_NAMES
    assert view["times"][0] == "09:00" and view["times"][-1] == "17:00"
    assert [person["name"] for person in view["people"]] == CALENDAR.people
    shown = next(person for person in view["people"] if person["name"] == PERSON)
    assert shown["busy"][0] == {
        "day": BUSY.day,
        "start": BUSY.start,
        "length": BUSY.length,
    }
    assert view["example"] == make_task(SEED).request
    assert view["limits"] == {"people": MAX_PEOPLE, "name_chars": MAX_NAME_CHARS}


def test_the_page_never_shows_a_practice_or_test_task():
    assert WEEKS <= PRACTICE_START < HELD_OUT_START


def test_schedule_reports_a_booking_at_a_free_time():
    result = schedule(args(), scripted(book(FREE)))
    assert result["outcome"] == "booked"
    assert result["booking"] == {
        "day": FREE.day,
        "start": FREE.start,
        "length": FREE.length,
        "attendees": [PERSON],
        "busy": [],
    }
    assert result["llm_calls"] == 1


def test_schedule_names_whoever_is_busy_at_the_booked_time():
    result = schedule(args(), scripted(book(BUSY)))
    assert result["booking"]["busy"] == [PERSON]


def test_schedule_reports_giving_up_with_the_reason():
    result = schedule(args(), scripted(call("give_up", reason="no time works")))
    assert result["outcome"] == "gave_up"
    assert result["booking"] is None
    assert result["reason"] == "no time works"


def test_schedule_reports_running_out_of_model_calls():
    talk = Reply(text="Let me think.")
    result = schedule(args(), scripted(talk, talk), max_turns=2)
    assert result["outcome"] == "out_of_turns"
    assert result["max_turns"] == 2
    assert result["events"] == [{"kind": "said", "text": "Let me think."}] * 2


def test_schedule_lists_what_the_model_wrote_and_did_in_order():
    result = schedule(
        args(agent="plain"),
        scripted(
            Reply(text="Checking."),
            call("get_busy", person="Zoya"),
            book(FREE),
        ),
    )
    assert [event["kind"] for event in result["events"]] == ["said", "tool", "tool"]
    assert result["events"][1] == {
        "kind": "tool",
        "tool": "get_busy",
        "args": {"person": "Zoya"},
        "result": "Error: unknown person: Zoya",
    }
    assert result["events"][2]["result"] == "Booked."


def test_schedule_gives_the_chosen_agent_its_own_tools_and_model():
    asked = []

    def llm_for(version):
        asked.append(version)
        return Script(call("find_slots", attendees=[PERSON], duration_minutes=30))

    result = schedule(args(agent="solver"), llm_for, max_turns=1)
    assert asked == [SOLVER]
    assert json.loads(result["events"][0]["result"])["count"] > 0

    # The plain agent has no find_slots tool.
    result = schedule(args(agent="plain"), llm_for, max_turns=1)
    assert asked == [SOLVER, PLAIN]
    assert result["events"][0]["result"].startswith("Error: there is no tool")


@pytest.mark.parametrize(
    "changes",
    [
        {"request": "   "},
        {"request": "x" * (MAX_REQUEST_CHARS + 1)},
        {"agent": "clever"},
        {"seed": -1},
        {"seed": WEEKS},
        {"extra": 1},
    ],
)
def test_schedule_args_reject_what_the_page_should_never_send(changes):
    with pytest.raises(ValidationError):
        args(**changes)


def test_schedule_args_trim_the_request():
    assert args(request="  Find a time.  ").request == "Find a time."


def own(*people, agent="solver"):
    """Schedule arguments with a calendar made by hand in place of a seed."""
    return ScheduleArgs(
        calendar={"people": list(people)}, request="Find a time.", agent=agent
    )


ASHA = {"name": "Asha", "busy": [{"day": 0, "start": 2, "length": 2}]}  # Mon 10:00-11:00


def test_a_calendar_made_by_hand_becomes_the_agents_calendar():
    later = {"day": 3, "start": 0, "length": 1}
    earlier = {"day": 0, "start": 4, "length": 2}
    made = own({"name": " Asha ", "busy": [later, earlier]}, {"name": "Vikram"})
    calendar = made.calendar.to_calendar()
    assert calendar.people == ["Asha", "Vikram"]
    assert [block.day for block in calendar.busy("Asha")] == [0, 3]
    assert calendar.busy("Vikram") == []


def test_schedule_uses_a_calendar_made_by_hand():
    def book_asha(start, end):
        return call("book", attendees=["Asha"], day="Monday", start=start, end=end)

    over_busy = schedule(own(ASHA), scripted(book_asha("10:30", "11:30")))
    assert over_busy["booking"]["busy"] == ["Asha"]

    # A meeting may start the moment a busy time ends.
    after = schedule(own(ASHA), scripted(book_asha("11:00", "12:00")))
    assert after["booking"] == {
        "day": 0,
        "start": 4,
        "length": 2,
        "attendees": ["Asha"],
        "busy": [],
    }

    # Only the people in that calendar exist.
    look = scripted(call("get_busy", person=PERSON))
    unknown = schedule(own(ASHA, agent="plain"), look, max_turns=1)
    assert unknown["events"][0]["result"] == f"Error: unknown person: {PERSON}"


@pytest.mark.parametrize(
    "people",
    [
        [],
        [{"name": f"Person {'abcdefghi'[n]}"} for n in range(MAX_PEOPLE + 1)],
        [{"name": "Asha"}, {"name": "asha"}],
        [{"name": ""}],
        [{"name": "A" * (MAX_NAME_CHARS + 1)}],
        [{"name": "R2D2"}],
        [{"name": '"; drop'}],
        [{"name": "Asha", "busy": [{"day": 5, "start": 0, "length": 1}]}],
        [{"name": "Asha", "busy": [{"day": 0, "start": 15, "length": 2}]}],
        [{"name": "Asha", "title": "extra"}],
    ],
)
def test_a_calendar_made_by_hand_is_checked(people):
    with pytest.raises(ValidationError):
        own(*people)


def test_names_may_use_any_alphabet_and_a_few_marks():
    made = own({"name": "Zoë"}, {"name": "Anne-Marie O'Neil"}, {"name": "मीरा"})
    assert made.calendar.to_calendar().people == sorted(
        ["Zoë", "Anne-Marie O'Neil", "मीरा"]
    )


def test_schedule_args_need_a_seed_or_a_calendar_but_not_both():
    with pytest.raises(ValidationError, match="either seed or calendar"):
        ScheduleArgs(request="Find a time.")
    with pytest.raises(ValidationError, match="either seed or calendar"):
        ScheduleArgs(seed=SEED, calendar={"people": [ASHA]}, request="Find a time.")


@pytest.fixture
def site():
    """The address of a running server whose model books a free time."""
    server = make_server(scripted(book(FREE)), port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, response.read()


def post(url, body, content_type="application/json"):
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": content_type}
    )
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read())


def error_of(send, *details):
    """The status and message of a request the server should refuse."""
    with pytest.raises(urllib.error.HTTPError) as caught:
        send(*details)
    return caught.value.code, json.loads(caught.value.read())["error"]


def test_site_serves_the_page(site):
    status, body = get(site + "/")
    assert status == 200
    assert b"<title>Scheduling agent</title>" in body


def test_site_serves_the_week_asked_for(site):
    status, body = get(f"{site}/api/week?seed={SEED}")
    assert status == 200
    assert json.loads(body) == week_view(SEED)


def test_site_picks_a_week_when_none_is_asked_for(site):
    seed = json.loads(get(site + "/api/week")[1])["seed"]
    assert 0 <= seed < WEEKS


def test_site_refuses_a_week_outside_its_range(site):
    status, message = error_of(get, f"{site}/api/week?seed={WEEKS}")
    assert status == 400
    assert message.startswith("seed:")


def test_site_runs_the_agent_on_a_posted_request(site):
    body = json.dumps({"seed": SEED, "request": "Find a time."}).encode()
    status, result = post(site + "/api/schedule", body)
    assert status == 200
    assert result["outcome"] == "booked"
    assert result["booking"]["attendees"] == [PERSON]


def test_site_runs_the_agent_on_a_calendar_made_by_hand(site):
    # The fake model books PERSON at a time that is free in the generated week.
    calendar = {"people": [{"name": PERSON, "busy": [FREE.model_dump()]}]}
    body = json.dumps({"calendar": calendar, "request": "Find a time."}).encode()
    status, result = post(site + "/api/schedule", body)
    assert status == 200
    assert result["booking"]["busy"] == [PERSON]

    both = json.dumps({"seed": SEED, "calendar": calendar, "request": "x"}).encode()
    assert error_of(post, site + "/api/schedule", both) == (
        400,
        "Value error, give either seed or calendar, not both",
    )


def test_site_refuses_a_request_it_cannot_use(site):
    url = site + "/api/schedule"
    assert error_of(post, url, b"{not json")[0] == 400
    assert error_of(post, url, b'{"seed": 7, "request": ""}') == (
        400,
        "request: String should have at least 1 character",
    )
    assert error_of(post, url, b"{}", "text/plain")[0] == 415
    assert error_of(post, url, b" " * (MAX_BODY_BYTES + 1))[0] == 413


def test_site_has_nothing_at_other_addresses(site):
    assert error_of(get, site + "/api/other") == (404, "not found")
    assert error_of(post, site + "/api/week", b"{}") == (404, "not found")


def test_site_stays_up_when_the_model_fails():
    def broken(version):
        raise ConnectionError("no model")

    server = make_server(broken, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        body = json.dumps({"seed": SEED, "request": "Find a time."}).encode()
        status, message = error_of(post, url + "/api/schedule", body)
        assert status == 500
        assert message == "the model could not run: no model"
        assert get(url + "/")[0] == 200
    finally:
        server.shutdown()
        server.server_close()
