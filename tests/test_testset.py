from pathlib import Path

import pytest

from schedagent.generator import make_task
from schedagent.sets import held_out_seeds
from schedagent.rules import MeetingRules, Window
from schedagent.testset import (
    check_worksheet,
    describe,
    load_test_tasks,
    read_worksheet,
    write_worksheet,
)

MON, TUE, WED, THU, FRI = range(5)
SEEDS = [5000, 5001, 5002]


def test_describe_states_the_rules_as_short_facts():
    rules = MeetingRules(
        attendees={"Ravi", "Meera"},
        length=2,
        must=Window(days={MON, TUE, WED, THU}, latest=6),
        prefer=Window(days={TUE}),
    )
    assert describe(rules) == {
        "Who": "Meera, Ravi",
        "Length": "1 hour",
        "Days (firm)": "not Friday",
        "Hours (firm)": "must end by 12:00",
        "Wish (optional)": "on Tuesday",
    }


def test_describe_with_no_limits_and_no_wish():
    rules = MeetingRules(attendees={"Ravi"}, length=1)
    facts = describe(rules)
    assert facts["Days (firm)"] == "any day"
    assert facts["Hours (firm)"] == "any time"
    assert facts["Wish (optional)"] == "none"


def test_describe_names_the_allowed_days_when_most_are_forbidden():
    rules = MeetingRules(
        attendees={"Ravi"},
        length=4,
        must=Window(days={TUE, WED}, earliest=8),
        prefer=Window(latest=6),
    )
    facts = describe(rules)
    assert facts["Length"] == "2 hours"
    assert facts["Days (firm)"] == "only Tuesday, Wednesday"
    assert facts["Hours (firm)"] == "cannot start before 13:00"
    assert facts["Wish (optional)"] == "end by 12:00"


def test_describe_two_forbidden_days_and_an_afternoon_wish():
    rules = MeetingRules(
        attendees={"Ravi"},
        length=3,
        must=Window(days={TUE, WED, THU}),
        prefer=Window(earliest=8),
    )
    facts = describe(rules)
    assert facts["Length"] == "90 minutes"
    assert facts["Days (firm)"] == "not Monday, not Friday"
    assert facts["Wish (optional)"] == "start at or after 13:00"


def test_a_new_worksheet_lists_every_task_with_no_request(tmp_path):
    path = tmp_path / "data" / "worksheet.txt"
    write_worksheet(path, SEEDS)
    text = path.read_text(encoding="utf-8")
    assert "Task 1 of 3 (seed 5000)" in text
    assert "Task 3 of 3 (seed 5002)" in text
    assert f"  Who: {describe(make_task(5000).rules)['Who']}" in text
    assert read_worksheet(path) == {5000: "", 5001: "", 5002: ""}


def test_the_worksheet_does_not_show_the_generated_request(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    text = path.read_text(encoding="utf-8")
    for seed in SEEDS:
        assert make_task(seed).request not in text


def test_an_existing_worksheet_is_never_replaced(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    path.write_text(path.read_text("utf-8") + "my work", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_worksheet(path, SEEDS)
    assert path.read_text("utf-8").endswith("my work")


def fill(path, requests):
    """Type a request after each 'Request:' line, in order."""
    lines = path.read_text(encoding="utf-8").splitlines()
    waiting = iter(requests)
    filled = [
        line + next(waiting) if line.startswith("Request:") else line for line in lines
    ]
    path.write_text("\n".join(filled) + "\n", encoding="utf-8")


def names(seed):
    return " and ".join(sorted(make_task(seed).rules.attendees))


def test_written_requests_are_read_back(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    fill(path, ["First one.", "Second one,\nwhich runs onto another line.", "Third."])
    assert read_worksheet(path) == {
        5000: "First one.",
        5001: "Second one, which runs onto another line.",
        5002: "Third.",
    }


def test_test_tasks_keep_the_generated_rules_and_use_the_written_request(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    fill(path, [f"Get {names(seed)} together." for seed in SEEDS])
    tasks = load_test_tasks(path, SEEDS)
    assert [task.seed for task in tasks] == SEEDS
    for task in tasks:
        generated = make_task(task.seed)
        assert task.rules == generated.rules
        assert task.calendar == generated.calendar
        assert task.request == f"Get {names(task.seed)} together."


def test_loading_fails_while_requests_are_missing(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    fill(path, [f"Get {names(5000)} together.", "", ""])
    with pytest.raises(ValueError, match="2 requests have not been written"):
        load_test_tasks(path, SEEDS)


def test_loading_fails_if_the_worksheet_is_for_other_tasks(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    with pytest.raises(ValueError, match="not the test set's tasks"):
        load_test_tasks(path, [5000, 5001])


def test_check_reports_missing_requests_and_wrong_names(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    attendees = sorted(make_task(5001).rules.attendees)
    outsider = next(
        name
        for name in ["Ravi", "Meera", "Arjun", "Divya", "Kabir", "Nisha", "Rohan", "Tara"]
        if name not in attendees
    )
    fill(
        path,
        [
            f"Get {names(5000)} together.",
            f"A meeting for {attendees[0]} and {outsider}.",
            "",
        ],
    )
    problems = check_worksheet(path, SEEDS)
    assert f"Task 2: mentions {outsider}, who is not attending" in problems
    for missing in attendees[1:]:
        assert f"Task 2: does not mention {missing}" in problems
    assert "Task 3: no request written yet" in problems
    assert not any(problem.startswith("Task 1:") for problem in problems)


def test_check_finds_nothing_wrong_with_complete_requests(tmp_path):
    path = tmp_path / "worksheet.txt"
    write_worksheet(path, SEEDS)
    fill(path, [f"Get {names(seed).lower()} together." for seed in SEEDS])
    assert check_worksheet(path, SEEDS) == []


def test_the_committed_test_set_is_complete():
    worksheet = Path(__file__).parents[1] / "data" / "test" / "worksheet.txt"
    seeds = held_out_seeds()
    tasks = load_test_tasks(worksheet, seeds)
    assert len(tasks) == 100
    assert check_worksheet(worksheet, seeds) == []
    # The requests are not the generated ones.
    assert all(task.request != make_task(task.seed).request for task in tasks)