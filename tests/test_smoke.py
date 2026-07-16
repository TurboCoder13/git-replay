"""Smoke test: the package imports and carries a version."""

from assertpy import assert_that

import git_replay


def test_package_has_version() -> None:
    """The package exposes a non-empty semver-ish version string."""
    assert_that(git_replay.__version__).is_not_empty()
    assert_that(git_replay.__version__.split(".")).is_length(3)
