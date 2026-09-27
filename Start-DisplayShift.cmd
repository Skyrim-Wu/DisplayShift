@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0config.windows-lg.json" (
    start "" "%~dp0dist\DisplayShift\DisplayShift.exe" --config "%~dp0config.windows-lg.json"
) else (
    start "" "%~dp0dist\DisplayShift\DisplayShift.exe"
)
