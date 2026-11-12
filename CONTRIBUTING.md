# Contributing to NetRescue

## Branches
- `main` is always working. Never push to it directly.
- One branch per member, named by area:
  `feat/topology`, `feat/routing`, `feat/monitoring`, `feat/dashboard`, `feat/experiments`.
- Work only inside your own folders. If you need a change somewhere else, ask the owner.

## Daily workflow
1. `git checkout main` then `git pull`
2. `git checkout feat/<your-area>` then `git merge main` (to stay up to date)
3. Make small changes and commit often.
4. `git push`
5. Open a pull request into `main`.

## Pull requests
- Every change goes through a pull request.
- Simrah or Zainab reviews and merges.
- Keep pull requests small and describe what was tested.
- Do not merge code that breaks `make topo`.

## Commit messages
Short and clear, for example:
- `Add ping probe parser`
- `Fix utilization calculation`

## Shared rules
- Code against `docs/api_contract.md` and `data/mock_metrics.json`.
- Mininet runs on one VM by one person at a time. Run `sudo mn -c` before and after every session.
- Do not commit large capture files or virtual environments.
- Daily check-in: what was done, what is next, what is blocked.
- Feature freeze at the end of Day 12.