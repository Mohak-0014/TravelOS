@echo off
REM Starts the full TravelOS local dev stack in four separate windows.
REM Infra (postgres/redis/qdrant) must already be up:
REM   docker compose -f infra/docker-compose.yml up -d postgres redis qdrant
REM Close a window (or Ctrl+C in it) to stop that service.

cd /d "%~dp0"

start "TravelOS backend" cmd /k backend\.venv\Scripts\uvicorn backend.api.main:app --reload --port 8000
start "TravelOS celery worker" cmd /k backend\.venv\Scripts\celery -A backend.workflows.celery_tasks worker --loglevel=info --pool=solo
start "TravelOS celery beat" cmd /k backend\.venv\Scripts\celery -A backend.workflows.celery_tasks beat --loglevel=info
start "TravelOS frontend" cmd /k "cd frontend && npm run dev"

echo All four services launching in separate windows.
echo Frontend: http://localhost:3000   Backend: http://localhost:8000
