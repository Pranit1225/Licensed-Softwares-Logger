@echo off
setlocal
set "INSTALL_DIR=%~dp0"
set "EXE=%INSTALL_DIR%LicenseLogger.exe"
set "TASK_NAME=License Usage Logger"

net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Run this file as Administrator.
    pause
    exit /b 1
)

if not exist "%EXE%" (
    echo ERROR: LicenseLogger.exe was not found in:
    echo %INSTALL_DIR%
    pause
    exit /b 1
)

schtasks /Create /TN "%TASK_NAME%" /TR "\"%EXE%\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
    echo ERROR: Failed to create scheduled task.
    pause
    exit /b 1
)

echo.
echo License Usage Logger task installed successfully.
echo It will start automatically when Windows starts.
echo The task runs as SYSTEM with highest privileges and has no visible console.
echo.
echo To start it now without rebooting:
schtasks /Run /TN "%TASK_NAME%"
echo.
pause
endlocal
