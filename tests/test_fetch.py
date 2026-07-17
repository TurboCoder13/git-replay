"""Tests for GitHub discovery and commit-log extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from assertpy import assert_that

from git_replay import fetch
from git_replay.repo import Repo

_FIXTURES = Path(__file__).parent / "fixtures"


def _repos_page() -> list[dict[str, object]]:
    """Load the fixture page mixing public, private, and fork repositories.

    Returns:
        The parsed repository objects from the fixture file.
    """
    payload: list[dict[str, object]] = json.loads(
        (_FIXTURES / "repos_page.json").read_text(encoding="utf-8"),
    )
    return payload


def test_discover_repos_drops_private_and_forks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Private and fork repositories are dropped unconditionally."""
    repos_page = _repos_page()
    monkeypatch.setattr(
        fetch,
        "_get_json",
        lambda url: repos_page if "&page=1" in url else [],
    )

    repos = fetch.discover_repos("TurboCoder13")

    names = [repo.name for repo in repos]
    assert_that(names).is_equal_to(["git-replay", "turbo-themes"])
    assert_that(names).does_not_contain("secret-lab")
    assert_that(names).does_not_contain("forked-tool")


def test_discover_repos_maps_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retained repositories carry owner, clone URL, and default branch."""
    repos_page = _repos_page()
    monkeypatch.setattr(
        fetch,
        "_get_json",
        lambda url: repos_page if "&page=1" in url else [],
    )

    repos = fetch.discover_repos("TurboCoder13")

    themes = next(repo for repo in repos if repo.name == "turbo-themes")
    assert_that(themes.owner).is_equal_to("TurboCoder13")
    assert_that(themes.default_branch).is_equal_to("develop")
    assert_that(themes.full_name).is_equal_to("TurboCoder13/turbo-themes")


def test_discover_repos_captures_head_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovered repositories carry the pushed_at marker as their head token."""
    repos_page = _repos_page()
    monkeypatch.setattr(
        fetch,
        "_get_json",
        lambda url: repos_page if "&page=1" in url else [],
    )

    repos = fetch.discover_repos("TurboCoder13")

    themes = next(repo for repo in repos if repo.name == "turbo-themes")
    assert_that(themes.head).is_equal_to("2026-01-10T00:00:00Z")


def test_external_head_returns_pushed_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A public external repository yields its pushed_at marker as the token."""
    monkeypatch.setattr(
        fetch,
        "_get_json_obj",
        lambda url: {"private": False, "pushed_at": "2026-02-02T00:00:00Z"},
    )

    assert_that(fetch.external_head("raycast/extensions")).is_equal_to(
        "2026-02-02T00:00:00Z",
    )


def test_external_head_returns_none_for_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A private external repository yields no token so it is skipped."""
    monkeypatch.setattr(fetch, "_get_json_obj", lambda url: {"private": True})

    assert_that(fetch.external_head("raycast/extensions")).is_none()


def test_discover_repos_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A full page triggers a follow-up request until a short page ends it."""
    full_page = [
        {
            "name": f"repo-{index}",
            "clone_url": f"https://github.com/o/repo-{index}.git",
            "default_branch": "main",
            "private": False,
            "fork": False,
        }
        for index in range(fetch._PER_PAGE)
    ]
    tail_page = [
        {
            "name": "repo-tail",
            "clone_url": "https://github.com/o/repo-tail.git",
            "default_branch": "main",
            "private": False,
            "fork": False,
        },
    ]

    def fake_get_json(url: str) -> list[dict[str, object]]:
        return tail_page if "&page=2" in url else full_page

    monkeypatch.setattr(fetch, "_get_json", fake_get_json)

    repos = fetch.discover_repos("o")

    assert_that(repos).is_length(fetch._PER_PAGE + 1)


def test_get_json_sets_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """When GH_TOKEN is set it is sent as a bearer authorization header."""
    captured: dict[str, Any] = {}

    class _Response:
        def read(self) -> bytes:
            return b"[]"

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any) -> _Response:
        captured["request"] = request
        return _Response()

    monkeypatch.setenv("GH_TOKEN", "s3cr3t")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)

    result = fetch._get_json("https://api.github.com/users/o/repos")

    assert_that(result).is_equal_to([])
    assert_that(captured["request"].get_header("Authorization")).is_equal_to(
        "Bearer s3cr3t",
    )


def test_get_json_without_token_omits_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without GH_TOKEN no authorization header is sent."""
    captured: dict[str, Any] = {}

    class _Response:
        def read(self) -> bytes:
            return b'[{"name": "x"}]'

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any) -> _Response:
        captured["request"] = request
        return _Response()

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)

    result = fetch._get_json("https://api.github.com/users/o/repos")

    assert_that(result).is_equal_to([{"name": "x"}])
    assert_that(captured["request"].get_header("Authorization")).is_none()


def test_dump_log_clones_and_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """dump_log clones bare and writes the captured log to a per-repo file."""
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> str:
        calls.append(args)
        if "clone" in args:
            return ""
        return "@1700000000\tEitel\tinitial\n1\t0\tREADME.md\n"

    monkeypatch.setattr(fetch, "_run", fake_run)
    repo = Repo(
        owner="TurboCoder13",
        name="git-replay",
        clone_url="https://github.com/TurboCoder13/git-replay.git",
        default_branch="main",
    )

    out_file = fetch.dump_log(repo=repo, out_dir=tmp_path)

    assert_that(str(out_file)).ends_with("TurboCoder13__git-replay.log")
    assert_that(out_file.read_text(encoding="utf-8")).contains("@1700000000")
    clone_args = calls[0]
    assert_that(clone_args).contains("--filter=blob:none")
    assert_that(clone_args).contains("--bare")
    log_args = calls[1]
    assert_that(log_args).contains("--no-merges")
    assert_that(log_args).contains("--numstat")
    assert_that(log_args).contains(f"--format={fetch._LOG_FORMAT}")


def test_get_json_rejects_non_https() -> None:
    """A non-https URL is rejected before any request is made."""
    with pytest.raises(ValueError):
        fetch._get_json("file:///etc/passwd")


def test_run_executes_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """_run captures stdout from the underlying subprocess call."""

    class _Completed:
        stdout = "ok\n"

    def fake_subprocess_run(args: list[str], **kwargs: object) -> _Completed:
        return _Completed()

    monkeypatch.setattr(fetch.subprocess, "run", fake_subprocess_run)

    assert_that(fetch._run(["git", "--version"])).is_equal_to("ok\n")


def _external_commit_item(
    sha: str,
    name: str = "Turbo Coder",
    parents: int = 1,
) -> dict[str, object]:
    """Build a REST commit-list item for external-repo tests."""
    return {
        "sha": sha,
        "parents": [{"sha": f"p{i}"} for i in range(parents)],
        "commit": {
            "message": f"subject for {sha}\n\nbody ignored",
            "author": {"name": name, "date": "2026-01-02T03:04:05Z"},
        },
    }


def test_dump_external_log_drops_private_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A private external repository is dropped unconditionally."""
    monkeypatch.setattr(fetch, "_get_json_obj", lambda url: {"private": True})
    result = fetch.dump_external_log(
        full_name="raycast/extensions",
        authors=["TurboCoder13"],
        out_dir=tmp_path,
    )
    assert_that(result).is_none()


def test_dump_external_log_writes_parseable_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """External commits round-trip through the standard log parser."""

    def fake_get_json_obj(url: str) -> dict[str, object]:
        if url.endswith("/repos/raycast/extensions"):
            return {"private": False}
        return {"stats": {"additions": 12, "deletions": 3}}

    def fake_get_json(url: str) -> list[dict[str, object]]:
        if "page=1" in url:
            return [
                _external_commit_item(sha="aaa"),
                _external_commit_item(sha="merge", parents=2),
                _external_commit_item(sha="aaa"),
            ]
        return []

    monkeypatch.setattr(fetch, "_get_json_obj", fake_get_json_obj)
    monkeypatch.setattr(fetch, "_get_json", fake_get_json)
    result = fetch.dump_external_log(
        full_name="raycast/extensions",
        authors=["TurboCoder13"],
        out_dir=tmp_path,
    )
    if result is None:  # pragma: no cover - fails the test above via assertpy
        raise AssertionError("expected a written log file")
    assert_that(result.name).is_equal_to("raycast__raycast-extensions.log")

    from git_replay.model import parse_log

    commits = parse_log(path=result, repo="raycast-extensions", aliases={})
    assert_that(commits).is_length(1)
    assert_that(commits[0].subject).is_equal_to("subject for aaa")
    assert_that(commits[0].ins).is_equal_to(12)
    assert_that(commits[0].dels).is_equal_to(3)


def test_dump_external_log_returns_none_when_no_commits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No matching commits yields no log file."""
    monkeypatch.setattr(fetch, "_get_json_obj", lambda url: {"private": False})
    monkeypatch.setattr(fetch, "_get_json", lambda url: [])
    result = fetch.dump_external_log(
        full_name="raycast/extensions",
        authors=["TurboCoder13"],
        out_dir=tmp_path,
    )
    assert_that(result).is_none()
