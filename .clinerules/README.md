- Project: Shared Shopping List PWA (FastAPI + SQLite).
- Environment: Development is Local Docker. Production is apoc.usbx.me (Port 19099).
- Architecture:
  * Backend: app/main.py (FastAPI).
  * Frontend: app/static/ (Single Page Application, Vanilla JS).
  * Database: app/data/shopping.db (SQLite).
- PWA Requirements: manifest.json and Service Worker for iOS "Add to Home Screen".
- Design Vibe: OLED light Mode, minimal borders, high contrast.
- Deployment: Use environment variables for PORT and HOST.
- Always refer to progress.md to see what task is next.
  * Before starting a task, change its status in progress.md to [ ] (In Progress).
  * Once a task is fully verified by adding relevant tests and running `make lint test`, mark it as [x].
  * If a new requirement pops up, add it to the 'To-Do' list immediately."
- Always add tests using unittest, ensure lint and tests pass before starting and before moving on.
- Prefer running commands from the Makefile, if important commands are missing add to 'To-Do'

use
```
docker compose
```
not docker-compose.

```
ssh apoc.usbx.me
```
to login to production, don't make changes here without asking. We will use uv for dependency management, to add new dependencies don't use pip but
```
uv add <python package> [--dev]
```
Use --dev if the dependency is for development only (lint/test).

To run code use
```
make lint test
uv run <file.py>
```

if a test fails, run only that test with e.g. to run only `test_touch_interactions`:
```
uv run python -m unittest discover tests -k test_touch_interactions
```