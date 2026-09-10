@echo off
setlocal
set "TASK_NAME=License Usage Logger"

net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Run this file as Administrator.
    pause
    exit /b 1
)

schtasks /Delete /TN "%TASK_NAME%" /F
if errorlevel 1 (
    echo Task removal failed or task does not exist.
) else (
    echo License Usage Logger task removed.
)
pause
endlocal
