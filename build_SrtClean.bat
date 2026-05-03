@echo off
cd /d "%~dp0"

echo Building SrtClean.exe ...
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python and add it to PATH.
    pause
    exit /b 1
)

python -m PyInstaller --onefile --console --name SrtClean SrtClean.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. Make sure required packages are installed:
    echo   pip install pyinstaller requests
    pause
    exit /b 1
)

echo.
echo Build complete! Output: dist\SrtClean.exe
echo Place SrtClean.json in the same folder as SrtClean.exe.
pause
