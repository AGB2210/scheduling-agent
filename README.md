# Scheduling agent

A small agent that books meetings from plain-language requests, running fully
on a local model.

The agent reads a request such as *"30 minutes with Ravi and Meera early next
week, not Friday, mornings preferred"*, checks calendars through tools, and
books a slot. The project measures how often the booking follows every hard
rule, and compares an agent that reasons alone against one that can call a
solver tool.

## Status

Work in progress. The agent runs on a local model and is being improved on a
practice set. There are no final results yet: the numbers so far come from the
practice set, which the agent has been tuned on. They are recorded, with the
changes that did not help, in [docs/experiments.md](docs/experiments.md).

## Running

Everything runs inside the project's own virtual environment, `.venv`. On
Windows, `start.bat` creates it the first time and installs the packages listed
in `pyproject.toml`. It needs Python 3.12 or newer.

```
start.bat
```

On its own, `start.bat` runs the tests. Anything written after it is passed to
the environment's Python, for example `start.bat -m pytest -q`.

To rebuild the environment, delete the `.venv` folder and run `start.bat`
again.

## The local model

The model runs through [Ollama](https://ollama.com). The project uses its own
copy, kept in the `ollama` folder, and nothing is installed on the machine. That
folder is not part of the repository.

1. Download `ollama-windows-amd64.zip` from the
   [Ollama releases page](https://github.com/ollama/ollama/releases) and unzip
   it into `ollama\bin`, so that `ollama\bin\ollama.exe` exists. The project
   was built with version 0.40.3.
2. Download a model into `ollama\models`:

   ```
   start.bat -m schedagent pull qwen2.5:3b
   ```

The project starts this copy of Ollama when it needs the model and stops it
afterwards. It listens on port 11435, not Ollama's usual port, so it does not
get mixed up with any other copy on the machine.

`qwen2.5:3b` is released under the Qwen Research License, which does not allow
commercial use.

## Running the model on the practice tasks

The practice set is 100 generated tasks: 80 that have a valid slot and 20 that
have none. It is for finding and fixing mistakes, not for reporting results.

```
start.bat -m schedagent run --model qwen2.5:3b --out runs\practice.jsonl
start.bat -m schedagent report runs\practice.jsonl
```

`run` saves one line per task, with every tool call the model made. If it is
interrupted, running the same command again carries on where it stopped.
`report` counts the outcomes.
