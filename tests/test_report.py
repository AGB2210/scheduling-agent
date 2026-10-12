from schedagent.report import format_comparison, format_summary, summarise


def record(grade, possible=True, problems=(), kept=None, steps=(), calls=2, seconds=1.0):
    return {
        "possible": possible,
        "grade": grade,
        "problems": list(problems),
        "kept_preference": kept,
        "steps": [{"tool": "get_busy", "args": {}, "result": result} for result in steps],
        "llm_calls": calls,
        "seconds": seconds,
    }


RECORDS = [
    record("correct", kept=True, steps=["[]", "Booked."], calls=2, seconds=1.0),
    record("correct", kept=False, steps=["Booked."], calls=1, seconds=2.0),
    record("correct", steps=["Error: unknown person: Zoya", "Booked."], calls=3),
    record("bad_booking", problems=["wrong length", "Ravi is busy", "Meera is busy"]),
    record("bad_booking", problems=["Ravi is busy"]),
    record("gave_up_wrongly", seconds=5.0),
    record("no_answer", calls=12, seconds=30.0),
    record("correct", possible=False),
    record("bad_booking", possible=False, problems=["day not allowed"]),
]


def test_summarise_counts_grades_for_each_kind_of_task():
    summary = summarise(RECORDS)
    assert summary["tasks"] == {"possible": 7, "impossible": 2}
    assert summary["grades"]["possible"] == {
        "correct": 3,
        "bad_booking": 2,
        "gave_up_wrongly": 1,
        "no_answer": 1,
    }
    assert summary["grades"]["impossible"] == {
        "correct": 1,
        "bad_booking": 1,
        "gave_up_wrongly": 0,
        "no_answer": 0,
    }


def test_summarise_counts_each_broken_rule_once_per_booking():
    # Two people busy in one booking is still one "someone is busy".
    assert summarise(RECORDS)["broken_rules"] == {
        "someone is busy": 2,
        "wrong length": 1,
        "day not allowed": 1,
    }


def test_summarise_counts_preferences_only_where_they_could_be_kept():
    summary = summarise(RECORDS)
    assert summary["preference_kept"] == 1
    assert summary["preference_missed"] == 1


def test_summarise_counts_tool_calls_and_errors():
    summary = summarise(RECORDS)
    assert summary["tool_calls"] == 5
    assert summary["tool_errors"] == 1


def test_summarise_averages_calls_and_time():
    summary = summarise(RECORDS)
    assert summary["mean_llm_calls"] == (2 + 1 + 3 + 2 + 2 + 2 + 12 + 2 + 2) / 9
    assert summary["median_seconds"] == 1.0


def test_format_summary_shows_the_main_numbers():
    text = format_summary({"model": "fake-model"}, summarise(RECORDS))
    assert "Model: fake-model" in text
    assert "possible         7        3  (43%)" in text
    assert "impossible       2        1  (50%)" in text
    assert "someone is busy      2" in text
    assert "Preference kept: 1 of 2" in text
    assert "Tool calls: 5, of which 1 came back as an error" in text


def graded(seed, grade, possible=True):
    return {"seed": seed, "grade": grade, "possible": possible}


def test_format_comparison_shows_each_run_and_the_difference_per_group():
    plain = [graded(n, "bad_booking") for n in range(8)]
    plain += [graded(8, "correct"), graded(9, "correct")]
    plain += [graded(n, "bad_booking", possible=False) for n in range(10, 14)]
    solver = [graded(n, "correct") for n in range(10)]
    solver += [graded(10, "correct", possible=False)]
    solver += [graded(n, "bad_booking", possible=False) for n in range(11, 14)]

    text = format_comparison("plain", plain, "solver", solver)
    assert "The difference is solver minus plain, task by task." in text
    possible, impossible = text.split("impossible tasks (4):")
    assert "possible tasks (10):" in possible
    assert "plain       20%" in possible
    assert "solver     100%  (100% to 100%)" in possible
    assert "difference  +80 points" in possible
    assert "plain        0%  (0% to 0%)" in impossible
    assert "solver      25%" in impossible
    assert "difference  +25 points" in impossible