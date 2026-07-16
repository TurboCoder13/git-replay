"""Repository record produced by GitHub discovery."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Repo:
    """A public, non-fork GitHub repository selected for replay.

    Attributes:
        owner: The login of the account that owns the repository.
        name: The repository name (without the owner prefix).
        clone_url: The HTTPS URL used to clone the repository.
        default_branch: The repository's default branch name.
    """

    owner: str
    name: str
    clone_url: str
    default_branch: str

    @property
    def full_name(self) -> str:
        """Return the ``owner/name`` identifier for the repository.

        Returns:
            The fully qualified repository name.
        """
        return f"{self.owner}/{self.name}"
