---
name: pre-commit
description: Run all SOP-6 pre-commit checks for TravelOS — ruff format/check, mypy, frontend lint/type-check, and pytest. Use before every commit to ensure nothing is broken.
disable-model-invocation: false
---

Run the full TravelOS pre-commit check sequence (SOP-6). Work through each step and report results clearly. Stop and flag errors immediately — don't continue past a failing step unless the user explicitly asks.

## Steps

1. **Backend lint + format** (from repo root):
   ```
   cd backend
   ruff format .
   ruff check .
   mypy .
   ```

2. **Frontend lint + type check** (only if frontend files changed):
   ```
   cd frontend
   npm run lint
   npm run type-check
   ```

3. **Tests**:
   ```
   cd backend
   pytest tests/ --cov=. --cov-report=term-missing
   ```
   Report: total pass/fail count and coverage percentage. Flag if coverage dropped below 80%.

4. **Secrets scan**:
   Run `git diff --staged` and scan for any `.env` file paths or obvious secrets (API keys, passwords, JWT secrets). Report if anything suspicious is staged.

## Output Format

Report each step as pass ✓ or fail ✗ with the relevant error output. If all steps pass, confirm the branch is ready to commit.
