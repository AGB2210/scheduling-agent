# Scheduling agent

[![tests](https://github.com/AGB2210/scheduling-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/AGB2210/scheduling-agent/actions/workflows/tests.yml)

A small agent that books meetings from plain-language requests, running fully
on a local model.

The agent reads a request such as *"30 minutes with Ravi and Meera early next
week, not Friday, mornings preferred"*, checks calendars through tools, and
books a slot. The project measures how often the booking follows every hard
rule, and compares an agent that reasons alone against one that can call a
solver tool.

## Results

Two versions of the agent were run once each on a test set of 100 tasks that
neither was tuned on. The plain agent reads the calendars and works out a time
itself. The solver agent states the request's rules to a tool that runs a
solver. Both use the same small model, `qwen2.5:3b`.

Share of tasks correct, with 95% confidence intervals:

| Tasks | Plain agent | Solver agent | Difference |
|---|---|---|---|
| A valid time exists (80) | 5% (1% to 10%) | 94% (88% to 99%) | +89 points (+81 to +95) |
| No valid time exists (20) | 0% | 30% (10% to 50%) | +30 points (+10 to +50) |

Handing the time arithmetic to a solver is what made the agent work. It still
rarely recognises a request that cannot be met, and books something instead of
giving up.

- [docs/results.md](docs/results.md) has the full results, the error analysis
  and the limits of what these numbers show.
- [docs/experiments.md](docs/experiments.md) records how the agent was built up
  on a practice set, including the changes that did not help.

## Running

Everything runs inside the project's own virtual environment, `.venv`. On
Windows, `start.bat` creates it the first time and installs the packages listed
in `pyproject.toml`. Each time it is run, it checks that those packages are
still there and installs any that are missing. It needs Python 3.12 or newer.

| Command | What it does |
|---|---|
| `start.bat` | Opens the web page for trying the agent (see below) |
| `start.bat test` | Runs the tests |
| `start.bat -m ...` | Passes anything else to the environment's Python, for example `start.bat -m pytest -q` |

The tests use fake models, so they need neither the local model nor a GPU.
GitHub Actions runs them on every push.

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

## Trying it in a browser

With the local model set up, running `start.bat` on its own, or double-clicking
it, opens a page for typing a request and watching the agent work on it:

```
start.bat
```

The page shows a generated week of calendars. Type a request for the people in
it and press Schedule. The page then shows each tool call the agent made, what
came back, and the time it booked, drawn on the calendars. Either agent can be
chosen.

"My calendar" swaps the generated week for one made by hand. Add people by
name, drag across a person's row to mark when they are busy, and click a busy
time to remove it. The calendar is kept in the browser, so it is still there
after a reload.

A typed request has no list of rules to grade it against, so the page checks
one thing only: whether anyone booked is busy at that time. The weeks it shows
are in neither the practice set nor the test set.

The page is a single HTML file served by Python's built-in web server, so it
adds no packages. It can be reached from this computer only, at
`http://127.0.0.1:8000`. Press Ctrl+C in the window that started it to stop
both the page and the model. `start.bat -m schedagent web --port 8001` uses
another port.

## Running the model on the practice tasks

The practice set is 100 generated tasks: 80 that have a valid slot and 20 that
have none. It is for finding and fixing mistakes, not for reporting results.

```
start.bat -m schedagent run --model qwen2.5:3b --out runs\practice.jsonl
start.bat -m schedagent report runs\practice.jsonl
```

`run` saves one line per task, with every tool call the model made. If it is
interrupted, running the same command again carries on where it stopped.
`report` counts the outcomes. Add `--agent solver` to `run` for the agent that
hands the rules to the solver; the default is the plain agent.

## The test set

The test set is 100 further tasks whose requests were written by the author, so
that the agent is measured on wording it was never tuned on. Each task's rules
are listed as plain facts in `data\test\worksheet.txt`, followed by the request
written for it.

```
start.bat -m schedagent check
start.bat -m schedagent run --set test --agent solver --model qwen2.5:3b --out runs\test-solver.jsonl
```

`check` lists requests that are missing or that name the wrong people. `run
--set test` refuses to start until every request is written.

## Licence

The code is released under the MIT licence; see [LICENSE](LICENSE). The model
is not part of this repository and has its own licence, noted above.
