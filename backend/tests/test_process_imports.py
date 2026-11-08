"""Standalone processes must see complete ORM metadata (the test process imports everything)."""

import subprocess
import sys

# Resolving every foreign key is what a flush does; it fails if a referenced table's
# module was never imported in that process.
RESOLVE_ALL = """
import relay.worker
from relay.shared.db.base import Base
for table in Base.metadata.tables.values():
    for fk in table.foreign_keys:
        fk.column
"""


def test_worker_process_resolves_every_foreign_key() -> None:
    result = subprocess.run(  # noqa: S603  (fixed interpreter and script)
        [sys.executable, "-c", RESOLVE_ALL], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
