# App Test Report

Run date: 15 November 2026
Platform: Windows, Python 3.12.0

## Automated tests

Command: `python -X utf8 -m pytest`

- `amalraj-testing`: 248 passed, 2 warnings in 84.62 seconds.
- `origin/improve/hackathon-judging-readiness` review worktree: 248 passed, 2 warnings in 83.05 seconds.

Both runs exercised the pipeline and Playwright app tests. The two warnings are `PytestRemovedIn10Warning` notices for class-scoped fixtures declared as instance methods.

## Browser check

The app on `amalraj-testing` was served at `http://127.0.0.1:8000/`. The review branch copy was served separately at `http://127.0.0.1:8002/`. The review copy loaded in the browser and showed the new introduction, evidence values, tour controls, safety note, and current-month panel.

## Limits

The checked-in processed app data was available. `data/raw/` is absent, so these checks did not rebuild the pipeline from NASA source files. The test command used `-X utf8` to avoid Windows' default `cp1252` decoding of UTF-8 project files.