"""Make random scheduling tasks whose right answers we can work out."""

import random
from dataclasses import dataclass

from schedagent.calendar import Calendar
from schedagent.request import write_request
from schedagent.rules import MeetingRules, Window
from schedagent.slots import DAYS, SLOTS_PER_DAY, Block

NAMES = ["Ravi", "Meera", "Arjun", "Divya", "Kabir", "Nisha", "Rohan", "Tara"]

MORNING = {"latest": 6}  # over by 12:00
AFTERNOON = {"earliest": 8}  # 13:00 or later


@dataclass(frozen=True)
class Task:
    """One scheduling problem: the calendars, the hidden rules, and the request."""

    seed: int
    calendar: Calendar
    rules: MeetingRules
    request: str


def make_task(seed: int) -> Task:
    """Build a task from a seed. The same seed always gives the same task."""
    rng = random.Random(seed)
    team = rng.sample(NAMES, k=rng.randint(3, 5))
    calendar = Calendar({person: _busy_week(rng) for person in team})
    rules = _make_rules(rng, team)
    request = write_request(rules, rng)
    return Task(seed=seed, calendar=calendar, rules=rules, request=request)


def _busy_week(rng: random.Random) -> list[Block]:
    """Up to three busy blocks a day that never overlap each other."""
    blocks: list[Block] = []
    for day in range(len(DAYS)):
        for _ in range(rng.randint(0, 3)):
            length = rng.randint(1, 4)
            start = rng.randint(0, SLOTS_PER_DAY - length)
            block = Block(day=day, start=start, length=length)
            if not any(block.clashes_with(taken) for taken in blocks):
                blocks.append(block)
    return sorted(blocks, key=lambda block: (block.day, block.start))


def _make_rules(rng: random.Random, team: list[str]) -> MeetingRules:
    attendees = rng.sample(team, k=rng.randint(2, 3))
    forbidden = rng.sample(range(len(DAYS)), k=rng.randint(0, 3))
    days = set(range(len(DAYS))) - set(forbidden)
    hours = rng.choice([{}, {}, MORNING, AFTERNOON])
    must = Window(days=days, **hours)
    return MeetingRules(
        attendees=attendees,
        length=rng.randint(1, 4),
        must=must,
        prefer=_make_preference(rng, must, limited_hours=bool(hours)),
    )


def _make_preference(
    rng: random.Random, must: Window, limited_hours: bool
) -> Window | None:
    """A preference the hard rules leave room for, or none at all."""
    options: list[Window | None] = [None]
    if not limited_hours:
        options += [Window(**MORNING), Window(**AFTERNOON)]
    if len(must.days) > 1:
        options.append(Window(days={rng.choice(sorted(must.days))}))
    return rng.choice(options)
