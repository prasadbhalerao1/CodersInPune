"""Text matching helpers shared by list filters and search."""


def like_pattern(q: str) -> str:
    """A `%q%` LIKE/ILIKE pattern in which the user's text is matched literally.

    `\\`, `%` and `_` are escaped with a backslash (PostgreSQL's default LIKE escape), so a
    search for "50%" or "a_b" finds exactly that instead of acting as a wildcard.

    Review fix (duplication). Before: this exact function was copied into catalog.assets,
    catalog.service and directory.service (and a fourth variant lived in search). Now: one
    definition. Why: an escaping rule must not be able to drift between copies.
    """
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
