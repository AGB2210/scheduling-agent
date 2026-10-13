"""Count what happened in a saved run."""

from collections import Counter
from statistics import mean, median

from schedagent.generator import make_task
from schedagent.stats import correct_rate, paired_difference
from schedagent.translation import FIELDS, compare, compare_wish, last_search

KINDS = ["correct", "bad_booking", "gave_up_wrongly", "no_answer"]


def summarise(records: list[dict]) -> dict:
    """Turn a run's task records into counts."""
    groups = {
        "possible": [record for record in records if record["possible"]],
        "impossible": [record for record in records if not record["possible"]],
    }
    grades = {
        name: {kind: sum(r["grade"] == kind for r in group) for kind in KINDS}
        for name, group in groups.items()
    }
    # A bad booking can break several rules, so these can add up to more
    # than the number of bad bookings.
    broken = Counter()
    for record in records:
        if record["grade"] == "bad_booking":
            broken.update({_rule(problem) for problem in record["problems"]})
    steps = [step for record in records for step in record["steps"]]
    return {
        "tasks": {name: len(group) for name, group in groups.items()},
        "grades": grades,
        "broken_rules": dict(broken.most_common()),
        "preference_kept": sum(r["kept_preference"] is True for r in records),
        "preference_missed": sum(r["kept_preference"] is False for r in records),
        "tool_calls": len(steps),
        "tool_errors": sum(step["result"].startswith("Error:") for step in steps),
        "mean_llm_calls": mean(r["llm_calls"] for r in records),
        "median_seconds": median(r["seconds"] for r in records),
    }


def _rule(problem: str) -> str:
    return "someone is busy" if problem.endswith(" is busy") else problem


def format_comparison(
    first_name: str, first: list[dict], second_name: str, second: list[dict]
) -> str:
    """Two runs on the same tasks, side by side, with 95% confidence intervals."""
    lines = [
        "Share of tasks correct, with 95% confidence intervals.",
        f"The difference is {second_name} minus {first_name}, task by task.",
    ]
    for group, possible in (("possible", True), ("impossible", False)):
        one = [record for record in first if record["possible"] == possible]
        two = [record for record in second if record["possible"] == possible]
        if not one:
            continue
        lines += [
            "",
            f"{group} tasks ({len(one)}):",
            f"  {first_name:10} {_percent(*correct_rate(one))}",
            f"  {second_name:10} {_percent(*correct_rate(two))}",
            f"  {'difference':10} {_points(*paired_difference(one, two))}",
        ]
    return "\n".join(lines)


def _percent(rate: float, interval: tuple[float, float]) -> str:
    return f"{rate:4.0%}  ({interval[0]:.0%} to {interval[1]:.0%})"


def _points(gain: float, interval: tuple[float, float]) -> str:
    return (
        f"{gain * 100:+4.0f} points  "
        f"({interval[0] * 100:+.0f} to {interval[1] * 100:+.0f})"
    )


def summarise_searches(records: list[dict]) -> dict:
    """For a run that used find_slots: how well each rule was stated.

    Looks at the last search the tool accepted in each task and compares it
    with that task's true rules.
    """
    counts = {field: Counter() for field in FIELDS}
    wishes = Counter()
    states_wishes = False
    tasks = 0
    for record in records:
        searched = last_search(record)
        if searched is None:
            continue
        tasks += 1
        true_rules = make_task(record["seed"]).rules
        for field, verdict in compare(searched, true_rules).items():
            counts[field][verdict] += 1
        wishes[compare_wish(searched, true_rules)] += 1
        states_wishes = states_wishes or searched.prefer is not None
    summary = {
        "tasks": tasks,
        "fields": {field: dict(counts[field]) for field in FIELDS},
    }
    # Only an agent that can state a wish apart from the rules is judged on it.
    if states_wishes:
        summary["wish"] = dict(wishes)
    return summary


def format_searches(summary: dict) -> str:
    lines = [
        f"How the last search stated each rule ({summary['tasks']} tasks with a search):",
        f"  {'':10}{'exact':>7}{'narrower':>10}{'wrong':>7}",
    ]
    for field, counts in summary["fields"].items():
        lines.append(
            f"  {field:10}{counts.get('exact', 0):>7}"
            f"{counts.get('narrower', 0):>10}{counts.get('wrong', 0):>7}"
        )
    if "wish" in summary:
        wish = summary["wish"]
        lines.append(
            f"The wish: {wish.get('exact', 0)} exact, "
            f"{wish.get('missing', 0)} missing, {wish.get('wrong', 0)} wrong"
        )
    return "\n".join(lines)


def format_summary(header: dict, summary: dict) -> str:
    lines = [f"Model: {header['model']}"]
    if "agent" in header:
        lines.append(f"Agent: {header['agent']} ({', '.join(header['tools'])})")
    lines.append("")
    lines.append(f"{'':12}{'tasks':>6}{'correct':>9}")
    for name, count in summary["tasks"].items():
        correct = summary["grades"][name]["correct"]
        share = f"({correct / count:.0%})" if count else ""
        lines.append(f"{name:12}{count:>6}{correct:>9}  {share}")
    for name, count in summary["tasks"].items():
        if count:
            lines += ["", f"What happened on {name} tasks:"]
            lines += [
                f"  {kind:18}{summary['grades'][name][kind]:>4}" for kind in KINDS
            ]
    if summary["broken_rules"]:
        lines += ["", "Rules broken by bad bookings (one booking can break several):"]
        lines += [
            f"  {rule:18}{count:>4}" for rule, count in summary["broken_rules"].items()
        ]
    could_keep = summary["preference_kept"] + summary["preference_missed"]
    lines += [
        "",
        f"Preference kept: {summary['preference_kept']} of {could_keep} "
        "correct bookings where it could be kept",
        f"Tool calls: {summary['tool_calls']}, "
        f"of which {summary['tool_errors']} came back as an error",
        f"Model calls per task: {summary['mean_llm_calls']:.1f} on average",
        f"Time per task: {summary['median_seconds']:.1f} s (median)",
    ]
    return "\n".join(lines)
