<!-- markdownlint-disable MD041 -- PR template does not start with a top-level heading -->

## Commit Summary (Conventional Commits)

- Title (required, present tense):

  ```text
  <type>(optional-scope): concise summary
  ```

  Examples: `feat(svg): add replay-bars renderer`, `fix(model): handle binary numstat`,
  `chore(ci): pin deploy action`

- Use squash merge so the PR title becomes the merge commit title.

## What's Changing

Describe the changes and why.

## Checklist

- [ ] Title follows Conventional Commits
- [ ] Tests added/updated
- [ ] Docs updated if user-facing
- [ ] Local checks passed (`uv run lintro chk && uv run pytest`)

## Closes

<!-- Every PR maps to an issue. Use `- Closes #123`. -->

- Closes #

## Details

Implementation notes and testing strategy.
