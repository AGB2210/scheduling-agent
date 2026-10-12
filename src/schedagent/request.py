"""Turn hidden rules into a plain-language request, using fixed templates."""

import random

from schedagent.rules import ALL_DAYS, MeetingRules, Window
from schedagent.slots import DAY_NAMES, SLOTS_PER_DAY, slot_to_time

LENGTHS = {
    1: ["30 minutes", "half an hour"],
    2: ["1 hour", "an hour", "60 minutes"],
    3: ["90 minutes", "an hour and a half"],
    4: ["2 hours", "two hours"],
}

OPENINGS = [
    "Set up a meeting for {people}. It should last {length}.",
    "{people} need to meet for {length}.",
    "Find {length} for {people} to meet.",
    "Please book {length} for a meeting between {people}.",
]

# Hard rules use firm words. Preferences use soft ones.
MUST_END_BY = [
    "It has to be finished by {time}.",
    "It must be over by {time}.",
    "Nothing after {time}.",
]
MUST_START_FROM = [
    "It can't start before {time}.",
    "It must start at {time} or later.",
    "Nothing before {time}.",
]
PREFER_END_BY = [
    "Ideally it would be over by {time}.",
    "If possible, have it finished by {time}.",
    "Preferably done by {time}, but that isn't essential.",
]
PREFER_START_FROM = [
    "Ideally it would start at {time} or later.",
    "If possible, not before {time}.",
    "Preferably {time} or later, but that isn't essential.",
]
PREFER_DAYS = [
    "Ideally on {days}.",
    "{days} would be best if it works.",
    "Preferably {days}, but that isn't essential.",
]


def write_request(rules: MeetingRules, rng: random.Random) -> str:
    """Describe the rules in words. The rng picks between phrasings."""
    people = rng.sample(sorted(rules.attendees), k=len(rules.attendees))
    opening = rng.choice(OPENINGS).format(
        people=_join(people, "and"), length=_length(rules.length, rng)
    )
    sentences = [opening, *_must(rules.must, rng)]
    if rules.prefer is not None:
        sentences += _prefer(rules.prefer, rng)
    return " ".join(sentences)


def _length(slots: int, rng: random.Random) -> str:
    if slots in LENGTHS:
        return rng.choice(LENGTHS[slots])
    return f"{slots * 30} minutes"


def _must(window: Window, rng: random.Random) -> list[str]:
    sentences = []
    allowed = [DAY_NAMES[day] for day in sorted(window.days)]
    forbidden = [DAY_NAMES[day] for day in sorted(ALL_DAYS - window.days)]
    if 1 <= len(forbidden) <= 2:
        is_or_are = "is" if len(forbidden) == 1 else "are"
        sentences.append(
            rng.choice(
                [
                    f"It can't be on {_join(forbidden, 'or')}.",
                    f"Not on {_join(forbidden, 'or')}.",
                    f"{_join(forbidden, 'and')} {is_or_are} out.",
                ]
            )
        )
    elif forbidden:
        sentences.append(
            rng.choice(
                [
                    f"It has to be on {_join(allowed, 'or')}.",
                    f"It must be on {_join(allowed, 'or')}.",
                    f"Only {_join(allowed, 'or')} will work.",
                ]
            )
        )
    if window.latest < SLOTS_PER_DAY:
        sentences.append(
            rng.choice(MUST_END_BY).format(time=slot_to_time(window.latest))
        )
    if window.earliest > 0:
        sentences.append(
            rng.choice(MUST_START_FROM).format(time=slot_to_time(window.earliest))
        )
    return sentences


def _prefer(window: Window, rng: random.Random) -> list[str]:
    sentences = []
    if window.days != ALL_DAYS:
        days = [DAY_NAMES[day] for day in sorted(window.days)]
        sentences.append(rng.choice(PREFER_DAYS).format(days=_join(days, "or")))
    if window.latest < SLOTS_PER_DAY:
        sentences.append(
            rng.choice(PREFER_END_BY).format(time=slot_to_time(window.latest))
        )
    if window.earliest > 0:
        sentences.append(
            rng.choice(PREFER_START_FROM).format(time=slot_to_time(window.earliest))
        )
    return sentences


def _join(words: list[str], last: str) -> str:
    """['a', 'b', 'c'] with 'or' becomes 'a, b or c'."""
    if len(words) == 1:
        return words[0]
    return f"{', '.join(words[:-1])} {last} {words[-1]}"
