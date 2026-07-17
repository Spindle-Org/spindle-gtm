# Runbook — GitHub, CI & release gate

## CI on pull requests
`.github/workflows/ci.yml` runs on every PR to `main` (and pushes to `main`/`feat/**`):
ruff format check → ruff lint → mypy → PII/export guard → pytest. **CI never accesses Apollo,
never sends email, and references no secrets** (`permissions: contents: read`, no `secrets.*`).

## Branch protection (set once, via UI or gh)
Protect `main`:
```sh
gh api -X PUT repos/Spindle-Org/spindle-gtm/branches/main/protection \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=quality' \
  -f 'enforce_admins=true' \
  -f 'required_pull_request_reviews[required_approving_review_count]=1' \
  -f 'restrictions='
```
Or Settings → Branches → Add rule for `main`: require PR, require the `quality` check, require
1 review (CODEOWNERS), no direct pushes.

## CODEOWNERS & required reviews
`.github/CODEOWNERS` routes safety-critical paths (compliance, gates, gateway, policy, config,
ADRs) to the founder. Keep review-required on `main`.

## Dependabot
`.github/dependabot.yml` opens weekly PRs for `uv` and GitHub Actions updates.

## Secret scanning (or local alternative)
Enable GitHub secret scanning + push protection (Settings → Code security), which needs
Advanced Security on private repos:
```sh
gh api -X PATCH repos/Spindle-Org/spindle-gtm \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```
If the plan lacks it, the **documented local alternative** is enforced already:
- pre-commit `detect-private-key`,
- the repo PII/export guard (`scripts/check_no_pii.py`) in pre-commit **and** CI,
- `.gitignore` excludes `.env*`, `data/`, `db/`, `exports/`, `logs/`, `outbox/`, `*.csv`,
  `*.sqlite*`, credential/token/oauth files,
- `doctor` + `release_gate.sh` assert no tracked secrets/PII.

## No production credentials in Actions
CI runs entirely on synthetic fixtures. Do not add Apollo/SMTP secrets to Actions. Anything
needing real credentials is a local, human-gated step.

## Release gate
```sh
make verify   # scripts/release_gate.sh
```
Passes only when: all tests pass, no tracked PII, no tracked secrets, real-write tools still
blocked (RealApolloClient refuses + kill switch engaged), and the synthetic end-to-end demo
works. The manual verifier prompts + first-real-send checklist gate the transition to real sends.
