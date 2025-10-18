@echo off
echo Starting real-time log streaming for CloudTasks...
echo Press Ctrl+C to stop
echo.

gcloud beta logging tail "resource.type=gae_app" --format="table(timestamp,severity,textPayload)"

pause
