"""Pure parsers for ownership evidence. No I/O, so they are unit-testable in isolation."""

from dataclasses import dataclass

import yaml

# Patterns that cover the whole repository (GitHub CODEOWNERS semantics).
_GLOBAL_PATTERNS = {"*", "/", "/*", "**", "/**"}
MAX_FILE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class OwnerEvidence:
    handle: str  # "@user", "@org/team", or a Backstage owner reference
    handle_type: str  # user | team | catalog
    source: str  # codeowners | catalog_info | maintainer
    detail: str  # the line, field or role that supports it
    repo_wide: bool  # True if it covers the whole repository


def parse_codeowners(content: str, path: str) -> list[OwnerEvidence]:
    evidence: list[OwnerEvidence] = []
    for number, raw in enumerate(content.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        for owner in owners:
            if not owner.startswith("@"):
                continue  # email owners can't be matched to GitHub handles deterministically
            evidence.append(
                OwnerEvidence(
                    handle=owner.lower(),
                    handle_type="team" if "/" in owner else "user",
                    source="codeowners",
                    detail=f"{path}:{number}  {pattern} {' '.join(owners)}"[:300],
                    repo_wide=pattern in _GLOBAL_PATTERNS,
                )
            )
    return evidence


def parse_catalog_info(content: str) -> list[OwnerEvidence]:
    """Backstage descriptor(s): `spec.owner` of each document (e.g. `group:platform`)."""
    try:
        documents = list(yaml.safe_load_all(content))
    except yaml.YAMLError:
        return []
    evidence: list[OwnerEvidence] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        spec, metadata = doc.get("spec"), doc.get("metadata")
        owner = spec.get("owner") if isinstance(spec, dict) else None
        if not isinstance(owner, str) or not owner.strip():
            continue
        name = metadata.get("name") if isinstance(metadata, dict) else None
        kind = doc.get("kind", "Component")
        evidence.append(
            OwnerEvidence(
                handle=owner.strip().lower(),
                handle_type="catalog",
                source="catalog_info",
                detail=f"catalog-info.yaml  {kind} {name or ''} spec.owner: {owner}"[:300],
                repo_wide=True,
            )
        )
    return evidence


def catalog_owner_slug(handle: str) -> str:
    """`group:default/platform` -> `platform`; `user:asha` -> `asha`; `platform` -> `platform`."""
    ref = handle.split(":", 1)[-1]
    return ref.rsplit("/", 1)[-1]
