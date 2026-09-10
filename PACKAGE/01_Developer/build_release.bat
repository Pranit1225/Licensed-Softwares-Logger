@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo License Logger - Windows EXE Build
 echo ==========================================

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found.
    echo Install it with: python -m pip install pyinstaller pywin32
    exit /b 1
)

python -m py_compile logger.py
if errorlevel 1 (
    echo Syntax check failed. Build cancelled.
    exit /b 1
)

python -m PyInstaller --onefile --noconsole --clean --name LicenseLogger logger.py
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

if not exist deployment mkdir deployment
copy /Y "dist\LicenseLogger.exe" "deployment\LicenseLogger.exe" >nul
copy /Y "tracked_apps.json" "deployment\tracked_apps.json" >nul
copy /Y "logger_config.json" "deployment\logger_config.json" >nul

if exist "deployment\Logger_Logs" rmdir /S /Q "deployment\Logger_Logs"
if exist "deployment\License_Usage" rmdir /S /Q "deployment\License_Usage"

echo.
echo Build complete.
echo Deployment files are in: %~dp0deployment
endlocal
