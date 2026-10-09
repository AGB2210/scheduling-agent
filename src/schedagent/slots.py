"""The working week as a grid of 30-minute slots."""

from pydantic import BaseModel, Field, model_validator

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
DAY_START_HOUR = 9
SLOT_MINUTES = 30
SLOTS_PER_DAY = 16  # 9:00 to 17:00


def slot_to_time(slot: int) -> str:
    """Turn a slot number into its start time, e.g. 10 -> '14:00'."""
    minutes = DAY_START_HOUR * 60 + slot * SLOT_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class Block(BaseModel, frozen=True):
    """A stretch of time on one day. The end slot is not included."""

    day: int = Field(ge=0, lt=len(DAYS))
    start: int = Field(ge=0, lt=SLOTS_PER_DAY)
    length: int = Field(gt=0)

    @model_validator(mode="after")
    def _fits_in_day(self):
        if self.end > SLOTS_PER_DAY:
            raise ValueError("block runs past the end of the working day")
        return self

    @property
    def end(self) -> int:
        return self.start + self.length

    def slots(self) -> range:
        return range(self.start, self.end)

    def clashes_with(self, other: "Block") -> bool:
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end
