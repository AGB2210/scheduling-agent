# Scheduling agent

A small agent that books meetings from plain-language requests, running fully
on a local model.

The agent reads a request such as *"30 minutes with Ravi and Meera early next
week, not Friday, mornings preferred"*, checks calendars through tools, and
books a slot. The project measures how often the booking follows every hard
rule, and compares an agent that reasons alone against one that can call a
solver tool.

## Status

Work in progress. The calendar world is being built first; there are no model
results yet.

## Running the tests

```
python -m pytest
```
