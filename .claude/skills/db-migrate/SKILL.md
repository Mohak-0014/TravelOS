---
name: db-migrate
description: Guided Alembic migration workflow per SOP-1. Use when adding or modifying database tables/columns. Accepts an optional description argument, e.g. /db-migrate add_hotel_candidates_table
disable-model-invocation: true
---

Run the TravelOS database migration workflow (SOP-1) for: $ARGUMENTS

## Steps

1. **Review ORM model changes** — confirm `backend/db/models.py` is updated with the intended schema changes before generating the migration.

2. **Generate migration**:
   ```
   cd backend
   alembic revision --autogenerate -m "$ARGUMENTS"
   ```

3. **Review the generated file** — open the new file in `backend/db/migrations/versions/`. Check for:
   - Missing enum type creation/dropping
   - Backfill logic for new NOT NULL columns
   - Correct `upgrade()` and `downgrade()` functions
   - Any server_default values needed for existing rows

   Prompt the user to confirm the migration looks correct before proceeding.

4. **Apply locally**:
   ```
   alembic upgrade head
   ```

5. **Verify** — run `alembic history` and confirm the new revision is at HEAD. Run the relevant tests to confirm nothing broke.

6. **Remind the user** — update `Documentations/DATABASE_SCHEMA.md` to reflect the schema change (DDL + ER description).

## Rules
- Never apply a migration to a shared/staging/production environment without the user's explicit confirmation.
- Never edit a migration file that has already been applied to any shared environment.
- If autogenerate produces an empty migration, stop and investigate — it may mean the ORM model wasn't saved or the DB is already in sync.
