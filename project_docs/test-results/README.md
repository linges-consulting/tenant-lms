# Test Results

Time-stamped snapshots of test runs (automated + browser smoke). Each run lives in its own file: `YYYY-MM-DD-<scope>.md`. Supporting artifacts (screenshots, console logs) go in subfolders next to the report.

| File | Coverage |
|---|---|
| [`2026-05-20-frontend.md`](2026-05-20-frontend.md) | Vitest full run + Playwright MCP browser smoke against the live stack |

## Conventions

- **One file per run.** Don't edit historic reports — append new ones.
- **Screenshots** live in `screenshots/` and use a `NN-<slug>.png` prefix that matches the order they appear in the report.
- **Raw command output** (vitest stdout, etc.) lives in `<repo-root>/tmp/` (gitignored) — keep only the curated summary here.
- **Findings** are the most valuable part. Anything surprising — flakes, perf regressions, real bugs discovered during the pass — goes under a "Findings" heading with a clear repro and a recommended next step.
