@echo off
echo CloudTasks Recent Logs
echo ======================

gcloud logging read "resource.type=gae_app" --limit=30 --format="value(timestamp,severity,textPayload)"

echo.
pause
