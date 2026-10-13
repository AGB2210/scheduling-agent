from schedagent.report import format_searches, summarise_searches
from schedagent.rules import MeetingRules, Window
from schedagent.translation import compare, compare_wish, last_search

MON, TUE, WED, THU, FRI = range(5)

# Ravi and Meera, 1 hour, not Friday, over by 12:00.
TRUE = MeetingRules(
    attendees={"Ravi", "Meera"},
    length=2,
    must=Window(days={MON, TUE, WED, THU}, latest=6),
)


def searched(**changes):
    fields = {
        "attendees": {"Ravi", "Meera"},
        "length": 2,
        "must": Window(days={MON, TUE, WED, THU}, latest=6),
    }
    return MeetingRules(**{**fields, **changes})


def step(result='{"count": 0, "slots": []}', **args):
    args = {"attendees": ["Ravi", "Meera"], "duration_minutes": 60, **args}
    return {"tool": "find_slots", "args": args, "result": result}


def test_a_search_that_matches_the_true_rules_is_exact_everywhere():
    assert compare(searched(), TRUE) == {
        "attendees": "exact",
        "length": "exact",
        "days": "exact",
        "hours": "exact",
    }


def test_fewer_days_is_narrower():
    verdict = compare(searched(must=Window(days={MON}, latest=6)), TRUE)
    assert verdict["days"] == "narrower"


def test_a_forbidden_day_is_wrong():
    verdict = compare(searched(must=Window(latest=6)), TRUE)  # all five days
    assert verdict["days"] == "wrong"


def test_swapping_allowed_and_forbidden_days_is_wrong():
    verdict = compare(searched(must=Window(days={FRI}, latest=6)), TRUE)
    assert verdict["days"] == "wrong"


def test_a_tighter_time_limit_is_narrower():
    verdict = compare(searched(must=Window(days={MON, TUE, WED, THU}, latest=4)), TRUE)
    assert verdict["hours"] == "narrower"


def test_a_looser_time_limit_is_wrong():
    verdict = compare(searched(must=Window(days={MON, TUE, WED, THU})), TRUE)
    assert verdict["hours"] == "wrong"


def test_the_wrong_people_or_length_is_wrong():
    assert compare(searched(attendees={"Ravi"}), TRUE)["attendees"] == "wrong"
    assert compare(searched(length=3), TRUE)["length"] == "wrong"


def test_last_search_reads_the_last_accepted_find_slots_call():
    record = {
        "steps": [
            step(days=["Monday"]),
            step(excluded_days=["Friday"], latest_end="12:00"),
            step(result="Error: days: Input should be a valid list", days="Tuesday"),
            {"tool": "book", "args": {}, "result": "Booked."},
        ]
    }
    assert last_search(record) == TRUE


def test_last_search_is_none_when_no_search_was_accepted():
    rejected = step(result="Error: unknown person: Zoya", attendees=["Zoya"])
    assert last_search({"steps": [rejected]}) is None
    assert last_search({"steps": []}) is None


def test_a_wish_stated_apart_from_the_rules_is_read_as_the_wish():
    record = {"steps": [step(excluded_days=["Friday"], latest_end="12:00", preferred_days=["Tuesday"])]}
    found = last_search(record)
    assert found.must == TRUE.must
    assert found.prefer == Window(days={TUE})


def test_the_wish_in_a_search_is_exact_missing_or_wrong():
    tuesday, monday = Window(days={TUE}), Window(days={MON})
    wants_tuesday = TRUE.model_copy(update={"prefer": tuesday})
    assert compare_wish(searched(), TRUE) == "exact"  # no wish, none stated
    assert compare_wish(searched(prefer=tuesday), wants_tuesday) == "exact"
    assert compare_wish(searched(), wants_tuesday) == "missing"
    assert compare_wish(searched(prefer=monday), wants_tuesday) == "wrong"
    assert compare_wish(searched(prefer=monday), TRUE) == "wrong"  # a wish from nowhere


def test_summarise_searches_judges_the_wish_only_when_one_was_stated():
    # Seed 1027: Meera and Kabir, two hours, 13:00 or later, ideally Monday.
    firm = {"attendees": ["Meera", "Kabir"], "duration_minutes": 120, "earliest_start": "13:00"}
    stated = step(**firm, preferred_days=["Monday"])
    left_out = step(**firm)
    as_a_rule = step(**firm, days=["Monday"])

    without = summarise_searches([{"seed": 1027, "steps": [as_a_rule]}])
    assert "wish" not in without
    assert "The wish" not in format_searches(without)

    summary = summarise_searches(
        [{"seed": 1027, "steps": [stated]}, {"seed": 1027, "steps": [left_out]}]
    )
    assert summary["wish"] == {"exact": 1, "missing": 1}
    assert summary["fields"]["days"] == {"exact": 2}
    assert "The wish: 1 exact, 1 missing, 0 wrong" in format_searches(summary)


def test_summarise_searches_counts_each_rule_across_tasks():
    # Seed 1000: Divya, Ravi and Meera, 90 minutes, not Tuesday, over by 12:00.
    people = ["Divya", "Ravi", "Meera"]
    exact = step(
        attendees=people, duration_minutes=90, excluded_days=["Tuesday"], latest_end="12:00"
    )
    forgot_the_day = step(attendees=people, duration_minutes=90, latest_end="12:00")
    with_the_wish = step(
        attendees=people, duration_minutes=90, days=["Friday"], latest_end="12:00"
    )
    records = [
        {"seed": 1000, "steps": [exact]},
        {"seed": 1000, "steps": [forgot_the_day]},
        {"seed": 1000, "steps": [with_the_wish]},
        {"seed": 1000, "steps": []},
    ]
    summary = summarise_searches(records)
    assert summary == {
        "tasks": 3,
        "fields": {
            "attendees": {"exact": 3},
            "length": {"exact": 3},
            "days": {"exact": 1, "wrong": 1, "narrower": 1},
            "hours": {"exact": 3},
        },
    }
    text = format_searches(summary)
    assert "3 tasks with a search" in text
    assert "days            1         1      1" in text
