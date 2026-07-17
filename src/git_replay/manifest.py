"""Persisted head-token manifest for incremental fetching.

The manifest records, per ``owner/name`` repository, the opaque head token
(the repository's ``pushed_at`` marker) captured the last time its commit log
was dumped. Comparing a freshly discovered token against the stored one lets a
fetch skip repositories that have not changed since the previous run.
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_NAME = "manifest.json"


def load_manifest(directory: str | Path) -> dict[str, str]:
    """Load the head-token manifest stored under ``directory``.

    A missing, unreadable, or malformed manifest yields an empty mapping so the
    caller re-dumps everything rather than trusting stale state.

    Args:
        directory: Directory that holds ``manifest.json`` alongside the logs.

    Returns:
        The stored ``{"owner/name": "<head-token>"}`` mapping, or an empty
        mapping when no valid manifest is present.
    """
    path = Path(directory) / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def save_manifest(directory: str | Path, manifest: dict[str, str]) -> Path:
    """Write ``manifest`` to ``manifest.json`` under ``directory``.

    Keys are sorted so repeated runs over unchanged inputs produce
    byte-identical files, keeping any content-derived cache keys stable.

    Args:
        directory: Directory to write ``manifest.json`` into.
        manifest: The ``{"owner/name": "<head-token>"}`` mapping to persist.

    Returns:
        The path of the written manifest file.
    """
    out_path = Path(directory)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path
