"""Command line for the project: start.bat -m schedagent <command>."""

import argparse
from pathlib import Path

from schedagent.generator import Task, make_task
from schedagent.local_model import local_model, model_options
from schedagent.report import (
    format_searches,
    format_summary,
    summarise,
    summarise_searches,
)
from schedagent.runner import load_run, run_set
from schedagent.server import running_ollama
from schedagent.sets import held_out_seeds, practice_seeds
from schedagent.testset import (
    WORKSHEET,
    check_worksheet,
    load_test_tasks,
    write_worksheet,
)
from schedagent.versions import VERSIONS, Version


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="schedagent")
    commands = parser.add_subparsers(dest="command", required=True)

    pull = commands.add_parser(
        "pull", help="download a model into the project's ollama folder"
    )
    pull.add_argument("model", help="an Ollama model name, such as qwen2.5:3b")

    run = commands.add_parser("run", help="run a model on a set of tasks")
    run.add_argument("--model", required=True)
    run.add_argument("--out", required=True, type=Path, help="file to save the run in")
    run.add_argument("--limit", type=int, help="only the first N tasks")
    run.add_argument(
        "--agent",
        choices=sorted(VERSIONS),
        default="plain",
        help="plain reads calendars itself; solver hands the rules to find_slots",
    )
    run.add_argument(
        "--set",
        choices=["practice", "test"],
        default="practice",
        help="practice has generated requests; test has separately written ones",
    )

    report = commands.add_parser("report", help="count what happened in a saved run")
    report.add_argument("run", type=Path)

    commands.add_parser(
        "worksheet", help="create the empty worksheet for writing test requests"
    )
    commands.add_parser("check", help="look for problems in the written test requests")

    args = parser.parse_args(argv)
    if args.command == "pull":
        _pull(args.model)
    elif args.command == "run":
        _run(args.model, args.out, args.limit, VERSIONS[args.agent], args.set)
    elif args.command == "report":
        header, records = load_run(args.run)
        print(format_summary(header, summarise(records)))
        searches = summarise_searches(records)
        if searches["tasks"]:
            print()
            print(format_searches(searches))
    elif args.command == "worksheet":
        write_worksheet(WORKSHEET, held_out_seeds())
        print(f"Created {WORKSHEET}. Write a request under each task.")
    else:
        problems = check_worksheet(WORKSHEET, held_out_seeds())
        print("\n".join(problems) if problems else "No problems found.")


def _pull(model: str) -> None:
    with running_ollama() as client:
        print(f"Downloading {model} ...")
        client.pull(model)
        for entry in client.list().models:
            print(f"{entry.model}: {entry.size / 1e9:.2f} GB")


def _tasks(set_name: str) -> list[Task]:
    if set_name == "test":
        return load_test_tasks(WORKSHEET, held_out_seeds())
    return [make_task(seed) for seed in practice_seeds()]


def _run(
    model: str, out: Path, limit: int | None, version: Version, set_name: str
) -> None:
    tasks = _tasks(set_name)[:limit]

    def show(record: dict) -> None:
        print(
            f"seed {record['seed']}: {record['grade']} "
            f"({record['llm_calls']} model calls, {record['seconds']} s)",
            flush=True,
        )

    settings = {"model": model, "options": model_options(), "set": set_name}
    with running_ollama() as client:
        llm = local_model(client, model, tools=version.tools)
        ran = run_set(tasks, llm, settings, out, on_task=show, version=version)
    print(f"Ran {ran} tasks. Saved in {out}")


if __name__ == "__main__":
    main()
