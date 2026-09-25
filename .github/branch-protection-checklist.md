# Branch and tag protection checklist

Scorecard `BranchProtection` / `CodeReview` alerts need GitHub Settings changes
(not only repository files). `CODEOWNERS` is in `.github/CODEOWNERS`.

Release tags are CalVer. This sketch does not publish to PyPI. `main` may carry
stable or pre-release tags later; `release/*` is for pre-releases only.

Apply or refresh via `scripts/apply_github_hardening.sh`. UI: https://github.com/marpi82/ha-atmos/settings/rules

## Branch ruleset: `main`

1. Require a pull request before merging
2. Require code owner review
3. Dismiss stale pull request approvals when new commits are pushed
4. Require conversation resolution before merging
5. Do **not** allow force pushes
6. Do **not** allow deletions
7. Require status checks: `secrets (gitleaks)`, `security (pip-audit)`, `quality (lint + typecheck)`, `tests (3.13)`, `hassfest`, `build`
8. Repository Admin may bypass (solo-maintainer)

## Branch ruleset: `release/**`

1. Require a pull request before merging
2. Do **not** allow force pushes
3. Restrict deletions
4. Repository Admin may bypass

## Tag ruleset (CalVer)

Patterns use fnmatch (`refs/tags/20*` and `refs/tags/v20*`):

1. Restrict tag creations
2. Block tag deletions
3. Block force updates of existing tags
4. Repository Admin may bypass (needed to cut releases)

## After enabling

Re-run the **Security Checks** workflow so Scorecard re-evaluates BranchProtection / CodeReview.
