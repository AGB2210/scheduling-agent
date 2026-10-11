"""Who is busy when."""

from schedagent.slots import Block


class UnknownPerson(LookupError):
    """Raised when a name is not in the calendar."""


class Calendar:
    """Each person's busy blocks for the week."""

    def __init__(self, busy: dict[str, list[Block]]):
        self._busy = {person: list(blocks) for person, blocks in busy.items()}

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Calendar) and self._busy == other._busy

    @property
    def people(self) -> list[str]:
        return sorted(self._busy)

    def busy(self, person: str) -> list[Block]:
        if person not in self._busy:
            raise UnknownPerson(person)
        return list(self._busy[person])

    def is_free(self, person: str, block: Block) -> bool:
        return not any(block.clashes_with(taken) for taken in self.busy(person))
