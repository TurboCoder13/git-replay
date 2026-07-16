# Contributing to git-replay

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Build

```bash
git clone https://github.com/TurboCoder13/git-replay.git
cd git-replay
uv sync
```

## Linting and Testing

We use [lintro](https://github.com/lgtm-hq/py-lintro) for linting and formatting.

```bash
uv run lintro chk   # lint
uv run lintro fmt   # format
uv run pytest       # tests with coverage
```

## Commits and Pull Requests

- Every PR maps to an issue; one PR per issue
- Use [Conventional Commits](https://www.conventionalcommits.org/) in PR titles
- Squash merge is required; the PR title becomes the merge commit
- Sign commits with `-s`
- Every PR must pass CI before merge

## Releases

There are none — output is deployed to GitHub Pages on merge and on a twice-weekly
schedule. No versioned artifacts are published.

## Questions

Open a [GitHub issue](https://github.com/TurboCoder13/git-replay/issues) or see
[SECURITY.md](SECURITY.md) for security reports.
