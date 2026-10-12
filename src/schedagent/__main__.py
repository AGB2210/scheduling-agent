"""Command line for the project: start.bat -m schedagent <command>."""

import argparse
from pathlib import Path

from schedagent.local_model import local_model, model_options
from schedagent.report import format_summary, summarise
from schedagent.runner import load_run, run_set
from schedagent.server import running_ollama
from schedagent.sets import practice_seeds
from schedagent.tools import TOOLS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="schedagent")
    commands = parser.add_subparsers(dest="command", required=True)

    pull = commands.add_parser(
        "pull", help="download a model into the project's ollama folder"
    )
    pull.add_argument("model", help="an Ollama model name, such as qwen2.5:3b")

    run = commands.add_parser("run", help="run a model on the practice tasks")
    run.add_argument("--model", required=True)
    run.add_argument("--out", required=True, type=Path, help="file to save the run in")
    run.add_argument("--limit", type=int, help="only the first N practice tasks")

    report = commands.add_parser("report", help="count what happened in a saved run")
    report.add_argument("run", type=Path)

    args = parser.parse_args(argv)
    if args.command == "pull":
        _pull(args.model)
    elif args.command == "run":
        _run(args.model, args.out, args.limit)
    else:
        header, records = load_run(args.run)
        print(format_summary(header, summarise(records)))


def _pull(model: str) -> None:
    with running_ollama() as client:
        print(f"Downloading {model} ...")
        client.pull(model)
        for entry in client.list().models:
            print(f"{entry.model}: {entry.size / 1e9:.2f} GB")


def _run(model: str, out: Path, limit: int | None) -> None:
    seeds = practice_seeds()[:limit]

    def show(record: dict) -> None:
        print(
            f"seed {record['seed']}: {record['grade']} "
            f"({record['llm_calls']} model calls, {record['seconds']} s)",
            flush=True,
        )

    settings = {"model": model, "options": model_options(), "tools": sorted(TOOLS)}
    with running_ollama() as client:
        ran = run_set(seeds, local_model(client, model), settings, out, on_task=show)
    print(f"Ran {ran} tasks. Saved in {out}")


if __name__ == "__main__":
    main()
