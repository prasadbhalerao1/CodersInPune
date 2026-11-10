"""Keyset pagination for long lists (NFR-PERF-005).

A page holds at most `limit` rows in a stable order. When more rows exist, the response
carries `X-Next-Cursor`: an opaque token naming the sort key of the page's last row, which
the client sends back as `after`. Lists are never silently truncated.
"""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from typing import Annotated, Any

from fastapi import Query, Response
from sqlalchemy import ColumnElement, tuple_
from sqlalchemy.orm import QueryableAttribute

from relay.shared.errors import ApiError

MAX_PAGE = 500
NEXT_HEADER = "X-Next-Cursor"
After = Annotated[str | None, Query(max_length=512, pattern=r"^[A-Za-z0-9_=-]+$")]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE)]


def encode(values: Sequence[object]) -> str:
    raw = json.dumps([v if isinstance(v, bool) else str(v) for v in values])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode(cursor: str, types: Sequence[Callable[[Any], object]]) -> list[object]:
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        if not isinstance(values, list) or len(values) != len(types):
            raise ValueError
        return [convert(v) for convert, v in zip(types, values, strict=True)]
    except ValueError, TypeError, binascii.Error, json.JSONDecodeError:
        raise ApiError(422, "invalid_cursor", "This page link is no longer valid.") from None


def after_key(
    columns: Sequence[ColumnElement[Any] | QueryableAttribute[Any]],
    cursor: str | None,
    types: Sequence[Callable[[Any], object]],
    *,
    descending: bool = False,
) -> ColumnElement[bool] | None:
    """The keyset condition for rows after `cursor` (None on the first page)."""
    if cursor is None:
        return None
    key = tuple_(*columns)
    position = tuple_(*decode(cursor, types))
    return key < position if descending else key > position


def split[T](
    rows: list[T], limit: int, key: Callable[[T], Sequence[object]]
) -> tuple[list[T], str | None]:
    """Rows were fetched with `limit + 1`; return the page and the next cursor, if any."""
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, encode(key(page[-1]))


def set_next(response: Response, cursor: str | None) -> None:
    if cursor is not None:
        response.headers[NEXT_HEADER] = cursor
