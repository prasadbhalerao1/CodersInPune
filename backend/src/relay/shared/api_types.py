"""Reusable request-field types."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


class StrictInput(BaseModel):
    """Base for request bodies: unknown fields are rejected, never silently ignored."""

    model_config = ConfigDict(extra="forbid")


def blank_to_none(value: str | None) -> str | None:
    return value or None
