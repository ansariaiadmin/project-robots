# Project Robots

This directory contains reusable project automation, not product code.

- Standard library only.
- Default commands are read-only or plan-only.
- Never delete project files.
- Store profiles and generated evidence inside `PROJECT_ROBOTS`, not target repos.
- Bind check evidence to the exact source fingerprint.
- Keep CLI output compact; detailed JSON belongs under `.cache/`.
- Add regression tests for routing, stale-evidence rejection, and filesystem safety.
