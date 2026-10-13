# Experiment log

A record of each run on the practice set: what was changed, why, the numbers
before and after, and what was concluded. It includes the changes that did not
help.

**These are practice-set numbers, not results.** The practice set was used to
find and fix mistakes, so the agent has been shaped by it. Final numbers will
come from a separate test set that is not used for any of this.

## What every run has in common

- Model: `qwen2.5:3b` (4-bit, Q4_K_M) run through Ollama 0.40.3 on an NVIDIA RTX
  3050 Laptop GPU with 4 GB of memory.
- Settings: temperature 0, seed 0, 8192 tokens of context, at most 512 tokens
  per reply, at most 12 model calls per task.
- Tasks: the 100 practice tasks from `practice_seeds()`. 80 have at least one
  valid slot ("possible") and 20 have none ("impossible").
- Each setup was run once.
- The saved runs are in `results/practice/`. Running
  `start.bat -m schedagent report results\practice\<file>` reproduces the
  counts below.

A task counts as correct when the agent books a slot that breaks no hard rule,
or gives up on a task that has no valid slot.

## Summary

| Run | Agent | What changed | Possible correct | Impossible correct | Tool calls rejected |
|---|---|---|---|---|---|
| 01 | plain | Starting point | 5 of 80 | 1 of 20 | 628 of 856 |
| 02 | plain | Removed the `list_people` tool | 5 of 80 | 1 of 20 | 16 of 467 |
| 03 | solver | `find_slots` in place of `get_busy` | 68 of 80 | 11 of 20 | 72 of 302 |
| 04 | solver | Added `excluded_days` | 58 of 80 | 12 of 20 | 92 of 298 |
| 05 | solver | `excluded_days` and worked examples | 63 of 80 | 16 of 20 | 4 of 218 |
| 06 | solver | Worked examples without `excluded_days` | 68 of 80 | 9 of 20 | 17 of 252 |
| 07 | solver | Run 05 plus a worked example of booking | 78 of 80 | 10 of 20 | 4 of 221 |

The plain agent reads calendars with `get_busy` and works out a time itself.
The solver agent states the request's rules to `find_slots`, which runs the
solver and returns the slots that fit.

## Before the first run: a reply that never ended

The first attempt at run 01 stalled on its third task. The model was writing a
single reply that had passed 15,000 tokens without stopping. A tool call needs
fewer than 100.

**Change:** each reply is now limited to 512 tokens. A reply cut off this way
counts as a turn with no tool call.

## Run 01: starting point (plain agent)

Code: commit `471463f`. Tools: `list_people`, `get_busy`, `book`, `give_up`.

| | Possible (80) | Impossible (20) |
|---|---|---|
| Correct | 5 | 1 |
| Booked a slot that breaks a rule | 42 | 10 |
| Gave up when a slot existed | 6 | 0 |
| No answer in 12 model calls | 27 | 9 |

628 of 856 tool calls were rejected. Nearly all were the same mistake: the
model wrapped its arguments in an extra layer, sending
`{"function": "get_busy", "type": "function", "arguments": {"person": "Ravi"}}`
where the tool expects `{"person": "Ravi"}`. Of the 36 tasks with no answer, 27
never had a single tool call accepted.

### Finding the cause

In the saved run, whether a call was malformed depended on the first tool the
model called, and the mistake then repeated:

| | Malformed |
|---|---|
| First call was `list_people` | 56 of 58 |
| First call was `get_busy` | 6 of 42 |
| Call following a clean call | 12 of 222 |
| Call following a malformed call | 491 of 534 |

A controlled test asked the model for only its first reply on each of the 100
tasks, changing only how the tools were described:

| Tools described to the model | Malformed first calls | Accepted first calls |
|---|---|---|
| As in run 01 | 63 | 32 |
| Same tools, with Pydantic's extra schema fields removed | 63 | 32 |
| Without `list_people` | 0 | 100 |

**Conclusion:** the cause was `list_people`, the only tool with no arguments.
The model filled the empty arguments with a copy of the layout the tools are
listed in, and then imitated its own earlier call for the rest of the task.
Tidying the schemas made no difference.

## Run 02: `list_people` removed (plain agent)

Code: commit `8c8e189`. The request already names the attendees, so the tool
was not needed.

| | Run 01 | Run 02 |
|---|---|---|
| Tool calls rejected | 628 of 856 | 16 of 467 |
| Tasks with no answer | 36 | 1 |
| Model calls per task (average) | 6.9 | 2.5 |
| Possible tasks correct | 5 of 80 | 5 of 80 |
| Impossible tasks correct | 1 of 20 | 1 of 20 |
| Bad bookings | 52 | 86 |

All 91 bookings were made after the model had read every attendee's calendar.
83 of the 86 bad bookings were at a time when an attendee was busy; 29 had the
wrong length and 21 were outside the allowed hours.

**Conclusion (a negative result):** removing the tool fixed the rejected calls
but did not improve correctness at all. The tasks that used to end with no
answer now end with a wrong booking. The model can fetch the calendars but
cannot work out a free time from them.

## Run 03: the solver agent

Code: commit `045f3e3`. Tools: `find_slots`, `book`, `give_up`. The model turns
the request into rules (who, how long, which days, which hours) and the solver
finds the slots.

| | Run 02 (plain) | Run 03 (solver) |
|---|---|---|
| Possible tasks correct | 5 of 80 | 68 of 80 |
| Impossible tasks correct | 1 of 20 | 11 of 20 |
| Bad bookings where an attendee was busy | 83 | 1 |
| Preference kept, where it could be | 1 of 1 | 34 of 39 |

How the last accepted search stated each rule, for the 98 tasks that had one.
"Narrower" leaves out times the true rules allow, which is what searching with
a wish included does. "Wrong" lets in something the true rules forbid.

| Rule | Exact | Narrower | Wrong |
|---|---|---|---|
| Attendees | 98 | 0 | 0 |
| Length | 98 | 0 | 0 |
| Days | 58 | 21 | 19 |
| Hours | 82 | 12 | 4 |

**Conclusion:** moving the slot arithmetic into code made the largest
difference of any change. The weak point became the day rule. For a request
such as "Monday and Wednesday are out", the model often sent
`days=["Monday", "Wednesday"]`, or left the days out.

**Caution:** 19 searches allowed a forbidden day but only 8 bookings were
marked wrong for the day. In the rest, the slot the model picked happened to
fall on an allowed day. Part of the 68 is luck.

## Run 04: `excluded_days` added (solver agent)

Code: not committed in this form. `find_slots` gained an `excluded_days`
argument, and the instructions gained one sentence saying when to use it. The
idea was that the model could copy the days a request rules out.

| | Run 03 | Run 04 |
|---|---|---|
| Possible tasks correct | 68 of 80 | 58 of 80 |
| Impossible tasks correct | 11 of 20 | 12 of 20 |
| Searches wrong on days | 19 of 98 | 16 of 95 |
| Tool calls rejected | 72 of 302 | 92 of 298 |

**Conclusion (a negative result):** the new argument did not fix the day rule.
The model mostly ignored it and still put any day named in the request into
`days`, including the forbidden ones. The guess behind the change, that
inverting a list was the difficulty, was wrong.

Task by task against run 03, 17 tasks got worse and 8 got better. Changing one
sentence of the instructions shifts many answers in both directions, so with
100 tasks this run shows only that the change did not help, not that it did
harm.

## Runs 05 and 06: worked examples (solver agent)

Three worked examples were added to the instructions. Each shows a request and
the `find_slots` arguments it should become. The examples use names, wording
and clock times that do not appear in the tasks.

- Run 05: examples, with `excluded_days`. Code: commit `bf000e8`.
- Run 06: the same examples rewritten to list the allowed days, and no
  `excluded_days` argument. This variant was run from a script and is not a
  committed state of the code; its instructions are saved in the run's header.

| | Run 03 | Run 04 | Run 05 | Run 06 |
|---|---|---|---|---|
| `excluded_days` | no | yes | yes | no |
| Worked examples | no | no | yes | yes |
| Possible tasks correct | 68 of 80 | 58 of 80 | 63 of 80 | 68 of 80 |
| Impossible tasks correct | 11 of 20 | 12 of 20 | 16 of 20 | 9 of 20 |
| Searches wrong on days | 19 of 98 | 16 of 95 | 2 of 100 | 13 of 100 |
| Searches wrong on hours | 4 of 98 | 2 of 95 | 4 of 100 | 8 of 100 |
| Tool calls rejected | 72 of 302 | 92 of 298 | 4 of 218 | 17 of 252 |

**Conclusions:**

- The two changes worked only together. `excluded_days` alone took the day
  mistakes from 19 to 16 and examples alone from 19 to 13. Both together took
  them to 2.
- The total number of correct tasks did not go up: 79 of 100 in run 03 and 79
  of 100 in run 05. Run 05 states the rules correctly far more often, so less
  of its score depends on luck.
- Run 05's setup was kept.

In run 05, 15 of the 18 bad bookings were one mistake at the booking step. The
search and the slots returned were right, but the model called `book` with the
start time of one returned slot and the end time of another, giving a meeting
of the wrong length.

## Run 07: a worked example of booking (solver agent)

One more example was added to the instructions: a list of slots as `find_slots`
returns them, followed by a `book` call that copies one slot's day, start and
end together. Nothing else changed from run 05.

| | Run 05 | Run 07 |
|---|---|---|
| Possible tasks correct | 63 of 80 | 78 of 80 |
| Impossible tasks correct | 16 of 20 | 10 of 20 |
| Bookings mixing two slots' start and end | 15 | 1 |
| Searches wrong on days | 2 of 100 | 3 of 100 |
| Searches wrong on hours | 4 of 100 | 6 of 100 |
| Tool calls rejected | 4 of 218 | 4 of 221 |
| Preference kept, where it could be | 26 of 35 | 33 of 42 |

Task by task against run 05, 15 tasks got better and 6 got worse.

**Conclusions:**

- The booking example removed the copying mistake, and possible tasks went from
  63 to 78 of 80.
- Impossible tasks got worse, from 16 to 10 of 20. All 10 failures are bookings
  on a task that has no valid slot. In 8 of them the search was wider than the
  true rules, so the solver returned slots that break a rule and the model
  booked one. In 2 the search correctly found nothing and the model booked a
  time anyway.
- An impossible task is unforgiving of a wide search. On a possible task a
  search that is too wide often still returns a valid slot first. On an
  impossible task every slot it returns is invalid.

Run 07's setup was kept. The remaining weak point is impossible tasks.

## Frozen for the test

Tuning stopped after run 07. The instructions and tools of both agents are
frozen as they are in commit `e9b23f7`, before any test request was written.
The known weakness on impossible tasks was left as it is, because every change
so far was fitted to the same 100 practice tasks.

The test set is 100 new tasks (80 possible, 20 impossible) from seeds that were
never used for practice. Their requests were written by the author, from a worksheet
that lists each task's rules as plain facts. Each agent is run on the test set
once, and that result is reported whatever it is.

## A second round, after the test

The test showed what the practice runs had already suggested: the solver agent
works on tasks that have a valid time and rarely gives up on tasks that have
none. Tuning was started again to work on that.

- The plain and solver agents stay exactly as they were tested, so their
  results can be reproduced. The changes go into a third version, `solver2`.
- Every change is tried on the practice set only.
- The first test set has been used and its failures have been read, so it
  cannot measure `solver2` fairly. It will not be run again. A new test set is
  needed before any result for `solver2` is reported.

The 12 tasks that run 07 got wrong were read one by one first:

| What the agent did | Tasks |
|---|---|
| The search found nothing, so it searched again without a firm rule and booked a slot from that | 7 |
| It booked a time that the search before it had not returned | 3 |
| It read "nothing after 12:00" as "start at 12:00 or later" | 1 |
| It searched with the wish included, found nothing, and gave up without searching again | 1 |

## Run 08: `book` only accepts a slot the search found (solver2)

In `solver2`, `book` refuses any time that the last `find_slots` did not find
for the same attendees. The refusal is an error message the model can read and
act on. The tool's description says so. The instructions did not change.

| | Run 07 (solver) | Run 08 (solver2) |
|---|---|---|
| Possible tasks correct | 78 of 80 | 78 of 80 |
| Impossible tasks correct | 10 of 20 | 12 of 20 |
| Bookings of a time the search had not found | 3 | 0 |
| Bad bookings | 11 | 7 |
| Tasks that ran out of model calls | 0 | 2 |
| Searches wrong on days | 3 of 100 | 3 of 100 |
| Searches wrong on hours | 6 of 100 | 5 of 100 |
| Tool calls rejected | 4 of 221 | 10 of 231 |
| Preference kept, where it could be | 33 of 42 | 31 of 42 |

Task by task against run 07, 3 tasks got better and 1 got worse. Taking each
task as a pair, impossible tasks changed by +10 points (0 to +25) and possible
tasks by 0 points (-4 to +4).

**Conclusions:**

- The bookings this change was aimed at are gone, and the tool now makes them
  impossible. Two of the three tasks became correct.
- The tool refused a booking only twice in the whole run, and both times the
  model then booked a slot it had been given. The other tasks changed because
  the tool's description changed, not because a booking was refused.
- The third task was not fixed. With no slot to book, the model searched again
  and again until its 12 model calls ran out. It still did not give up.
- One task that was correct now fails: the model kept adding an argument that
  `find_slots` does not have. Any change to the wording moves a few tasks.
- With 20 impossible tasks, a change of 2 tasks is weak evidence. The change
  was kept because it removes one kind of mistake for certain and nothing
  measured got worse on possible tasks.
- All 7 bad bookings left are on impossible tasks. In 6 the search found
  nothing and the model searched again without a firm rule. In 1 it misread a
  time limit. Run 08 did nothing about these.

## Run 09: the wish goes in the same search (solver2)

Until now the agent searched with a wish included and, if that found nothing,
searched again without it. That second search is where it left out firm rules.
In run 09 `find_slots` takes the wish in its own arguments (`preferred_days`,
`preferred_earliest_start`, `preferred_latest_end`) next to the firm rules.
The tool returns the slots that keep the wish when there are some, and the
slots that follow the firm rules when there are none. The instructions now say
to search once, to give up when the search returns nothing, and never to
search again with fewer rules. The three example requests are the same as
before, each now shown with one search.

| | Run 08 | Run 09 |
|---|---|---|
| Possible tasks correct | 78 of 80 | 79 of 80 |
| Impossible tasks correct | 12 of 20 | 17 of 20 |
| Bad bookings | 7 | 4 |
| Tasks that ran out of model calls | 2 | 0 |
| Gave up although a valid slot existed | 1 | 0 |
| Searches wrong on days | 3 of 100 | 0 of 100 |
| Searches narrower than the rules on days | 16 of 100 | 2 of 100 |
| Searches wrong on hours | 5 of 100 | 11 of 100 |
| Tool calls rejected | 10 of 231 | 9 of 212 |
| Preference kept, where it could be | 31 of 42 | 41 of 43 |

Task by task against run 08, 7 tasks got better and 1 got worse. Taking each
task as a pair, impossible tasks changed by +25 points (0 to +50) and possible
tasks by +1 point (0 to +4).

**Conclusions:**

- Impossible tasks went from 12 to 17 of 20. Of the 6 tasks where run 08
  searched again without a firm rule, 4 are now correct. With one search there
  is no second search to get wrong.
- The wish is kept far more often, 41 of 43 against 31 of 42, because the tool
  now offers only the slots that keep it.
- The change brought a new mistake. In 11 of the 36 tasks with a firm start
  time ("It must start at 13:00 or later", "Nothing before 13:00"), the model
  put that time in `preferred_earliest_start`, as if it were a wish. A firm end
  time was stated correctly in all 29 tasks that have one.
- All 4 tasks that failed in run 09 have this mistake. The other 7 tasks with
  it were still graded correct, because the slot booked happened to be valid.
- A likely cause, not yet tested: the only example in the instructions that
  has a start time is a wish ("After 10:00 would be nice"). No example shows a
  firm start time.

Run 09's setup was kept.
