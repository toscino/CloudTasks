@echo off
echo Starting Firestore Test App...
echo.

REM Load environment variables from .env file
if exist .env (
    echo Loading environment variables from .env file...
    for /f "usebackq tokens=1,2 delims==" %%a in (.env) do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            set "%%a=%%b"
        )
    )
) else (
    echo Warning: .env file not found, using default values
    set GOOGLE_CLOUD_PROJECT=crucial-haiku-473123-r7
)

echo Using Google Cloud Project: %GOOGLE_CLOUD_PROJECT%
echo Available Demo Users:
echo   Ian: %USER1_SECRET_KEY%
echo   Karleigh: %USER2_SECRET_KEY%
echo   User3: %USER3_SECRET_KEY%
echo.
echo The app will start and automatically open in your browser...
echo.
echo Test URLs:
echo   Test User (no key): http://127.0.0.1:8080/
echo   Ian: http://127.0.0.1:8080/?secret_key=%USER1_SECRET_KEY%
echo   Karleigh: http://127.0.0.1:8080/?secret_key=%USER2_SECRET_KEY%
echo   User3: http://127.0.0.1:8080/?secret_key=%USER3_SECRET_KEY%
echo.
echo Press Ctrl+C to stop the server
echo.
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8080/?secret_key=%USER1_SECRET_KEY%
python main.py
