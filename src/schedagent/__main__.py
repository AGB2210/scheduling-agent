"""Command line for the project: start.bat -m schedagent <command>."""

import argparse

from schedagent.server import running_ollama


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="schedagent")
    commands = parser.add_subparsers(dest="command", required=True)
    pull = commands.add_parser(
        "pull", help="download a model into the project's ollama folder"
    )
    pull.add_argument("model", help="an Ollama model name, such as qwen2.5:3b")
    args = parser.parse_args(argv)

    if args.command == "pull":
        with running_ollama() as client:
            print(f"Downloading {args.model} ...")
            client.pull(args.model)
            for entry in client.list().models:
                print(f"{entry.model}: {entry.size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
