# SwipeSwitch Git Workflow

## Repository setup

After extracting the project, initialise the repository from its root:

```bash
git init
git add .
git commit -m "chore: establish SwipeSwitch project baseline"
```

Before committing, review `git status` and confirm that no personal configuration, device-specific logs, virtual environments, generated packages or credentials are included.

## Branching

- `main` contains the latest known-good baseline.
- Use short-lived feature branches for milestone work, for example `feature/gesture-recognition` or `fix/libinput-parser`.
- Keep each commit focused on one coherent change.
- Do not merge a feature until its stated tests and verification steps have been completed or its limitations are explicitly recorded.

## Commit conventions

Use a concise type prefix:

- `feat:` new user-facing capability
- `fix:` defect correction
- `refactor:` internal restructuring without intended behaviour change
- `test:` tests and fixtures
- `docs:` documentation-only change
- `build:` packaging, dependencies or tooling
- `chore:` maintenance work

Examples:

```text
fix: parse libinput swipe updates with sequence numbers
feat: add four-finger workspace navigation
test: cover cancelled gesture lifecycle
docs: record Show Desktop restoration behaviour
```

## Milestone discipline

At the end of each milestone:

- Update the changelog and implementation status.
- Record commands run and their results.
- Distinguish unit, integration and manual verification.
- Record known limitations and deferred work.
- Tag a milestone only after its exit criteria are met.

Never label a milestone complete solely because code has been written.
