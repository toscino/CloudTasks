@echo off
echo CloudTasks Log Viewer
echo ====================
echo.
echo 1. Real-time streaming (tail)
echo 2. Recent logs (last 100)
echo 3. Error logs only
echo 4. INFO level and above
echo 5. Custom filter
echo.
set /p choice="Choose option (1-5): "

if "%choice%"=="1" (
    echo Starting real-time log streaming...
    gcloud beta logging tail "resource.type=gae_app" --format="table(timestamp,severity,textPayload)"
) else if "%choice%"=="2" (
    echo Showing last 100 logs...
    gcloud logging read "resource.type=gae_app" --limit=100 --format="table(timestamp,severity,textPayload)"
) else if "%choice%"=="3" (
    echo Showing error logs only...
    gcloud logging read "resource.type=gae_app AND severity>=ERROR" --limit=50 --format="table(timestamp,severity,textPayload)"
) else if "%choice%"=="4" (
    echo Showing INFO level and above...
    gcloud logging read "resource.type=gae_app AND severity>=INFO" --limit=50 --format="table(timestamp,severity,textPayload)" --order="desc"
) else if "%choice%"=="5" (
    set /p filter="Enter custom filter (e.g., 'textPayload:\"task\"'): "
    gcloud logging read "resource.type=gae_app AND %filter%" --limit=50 --format="table(timestamp,severity,textPayload)" --order="desc"
) else (
    echo Invalid choice
)

echo.
pause
