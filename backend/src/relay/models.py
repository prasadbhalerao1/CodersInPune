"""Imports every ORM module so the shared metadata is complete in any process.

Cross-module foreign keys (e.g. `platform.tenant`) only resolve once the target table is
registered; processes that don't import every router (the worker, Alembic) rely on this.
"""

import relay.audit.models
import relay.catalog.models
import relay.continuity.models
import relay.directory.models
import relay.identity.models
import relay.integrations.github.models
import relay.jobs.models
import relay.platform.models  # noqa: F401
