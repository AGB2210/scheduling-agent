# Results

These are the results on the test set. How the agent got to this point,
including the changes that did not help, is in [experiments.md](experiments.md).

## What was measured

Two versions of the agent were compared on the same 100 tasks:

- The **plain agent** reads each attendee's calendar with a tool and works out
  a free time itself.
- The **solver agent** states the request's rules to a tool, which runs a solver
  over the calendars and returns the times that fit.

Both use the same model, `qwen2.5:3b`, with the same settings. They differ in
one tool and in their instructions.

A task is **correct** when the agent books a time that breaks no firm rule, or
gives up on a task that has no valid time. A task where a valid time exists is
called *possible*; one where none exists is called *impossible*.

## The test set

- 100 tasks: 80 possible and 20 impossible, from seeds that were never used
  while building or tuning the agent.
- The calendars and rules are generated. The requests were written by the
  author from a list of each task's rules, not produced by the templates used
  for practice.
- Both agents were frozen before the requests were written, and the test set
  was committed before either agent was run on it.
- Each agent was run on the test set once. Nothing was changed afterwards.

## Results

Share of tasks correct, with 95% confidence intervals.

| Tasks | Plain agent | Solver agent | Difference |
|---|---|---|---|
| Possible (80) | 4 of 80, 5% (1% to 10%) | 75 of 80, 94% (88% to 99%) | +89 points (+81 to +95) |
| Impossible (20) | 0 of 20, 0% (see note) | 6 of 20, 30% (10% to 50%) | +30 points (+10 to +50) |

The intervals come from a bootstrap with 10,000 resamples. The difference is
taken task by task, since both agents ran on the same tasks.

**Note on 0 of 20.** The bootstrap gives an interval of 0% to 0% here, because
every resample of twenty failures is twenty failures. That understates the
uncertainty. An exact binomial interval for 0 of 20 is 0% to 17%.

## What this shows

- **Moving the time arithmetic out of the model made the difference.** On tasks
  that have a valid time, the solver agent was correct on 75 of 80 and the
  plain agent on 4 of 80. The interval for the difference, +81 to +95 points,
  is far from zero.
- **The plain agent's failure is not a tool-use failure.** It made 532 tool
  calls and 28 were rejected. It then booked a time when an attendee was busy
  in 85 of its 89 bad bookings.
- **Impossible tasks remain unsolved.** The solver agent recognised only 6 of
  the 20 tasks that have no valid time. With 20 tasks the interval is wide, 10%
  to 50%, but all of it is well below the 94% on possible tasks.

## How the solver agent stated the rules

For each task, the last search the tool accepted was compared with the task's
true rules. "Narrower" leaves out times the rules allow, which is what
searching with a wish included does. "Wrong" lets in something the rules
forbid.

| Rule | Exact | Narrower | Wrong |
|---|---|---|---|
| Attendees | 100 | 0 | 0 |
| Length | 100 | 0 | 0 |
| Days | 74 | 22 | 4 |
| Hours | 67 | 28 | 5 |

Other measurements for the solver agent on the test set:

- A wish in the request was kept in 49 of the 51 correct bookings where a valid
  time could keep it.
- 5 of 226 tool calls were rejected.
- A task took 2.5 model calls on average and 1.7 seconds (median).

## Where the solver agent failed

It failed 19 of the 100 tasks: 5 possible and 14 impossible. Of those, 17 were
bookings that break a rule:

| What happened | Count |
|---|---|
| The search was wider than the true rules, and the agent booked a time it returned | 9 |
| The search correctly found nothing, and the agent booked a time anyway | 5 |
| The search was right, and the agent booked one slot's start with another's end | 3 |

The other two were one task where it gave up although a valid time existed, and
one where it reached the limit of 12 model calls without answering.

An impossible task is unforgiving of a search that is too wide. On a possible
task such a search often still returns a valid time first. On an impossible
task every time it returns is invalid.

## Practice set and test set

| | Practice set (run 07) | Test set |
|---|---|---|
| Solver agent, possible tasks | 78 of 80 | 75 of 80 |
| Solver agent, impossible tasks | 10 of 20 | 6 of 20 |

The result on possible tasks held up on requests the agent was not tuned on.
The result on impossible tasks was lower.

## Limits of these results

- **One model, one run.** Everything is from `qwen2.5:3b` at temperature 0,
  with each agent run once. Other models may behave differently.
- **Few impossible tasks.** Twenty tasks give a wide interval.
- **Generated tasks.** The calendars and rules come from a simple generator: a
  single week from Monday to Friday, half-hour steps, two or three attendees,
  and a small set of rule kinds.
- **Tidy requests.** The test requests are complete, well-formed sentences that
  state every rule. Real messages are often shorter, vaguer or incomplete.
- **Requests were checked against their rules before the test.** 18 of the 100
  were reworded so that they say what their task's rules say: 13 that said
  "afternoon" where the rule is 13:00, 4 that named a day the calendar does not
  have, and 1 that stated a wish as a requirement. This was done before either
  agent was run on the test set.
- **Tuned on similar tasks.** The solver agent's instructions and tool were
  adjusted on a practice set from the same generator.
- **No questions.** The agent cannot ask the person for more information. It
  can only book or give up.

## Reproducing

The saved runs are in `results/test/`.

```
start.bat -m schedagent report results\test\solver.jsonl
start.bat -m schedagent report results\test\plain.jsonl
start.bat -m schedagent compare results\test\plain.jsonl results\test\solver.jsonl
```

To run the agents again, which needs the local model set up as described in
the README:

```
start.bat -m schedagent run --set test --agent solver --model qwen2.5:3b --out runs\test-solver.jsonl
start.bat -m schedagent run --set test --agent plain --model qwen2.5:3b --out runs\test-plain.jsonl
```
