@echo off
echo Setting up Google Cloud SDK PATH for this session...
set PATH=%PATH%;"C:\Users\ianmb\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"
echo Google Cloud SDK added to PATH
echo.
echo Testing gcloud...
gcloud.cmd --version
echo.
echo You can now use gcloud commands!
echo To make this permanent, add the path to your system environment variables.
