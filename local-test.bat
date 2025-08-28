@echo off
echo ========================================
echo 🐂 Yak Analyzer Local Test (No Docker)
echo ========================================

if not exist "test_env" (
    echo [1/5] Creating Python virtual environment...
    python -m venv test_env
)

echo [2/5] Activating environment...
call test_env\Scripts\activate

echo [3/5] Installing basic dependencies...
pip install flask pillow imagehash --quiet

echo [4/5] Starting application...
set PYTHONPATH=%cd%\src
start "" python run.py

echo [5/5] Waiting for startup...
timeout /t 5

echo.
echo ========================================
echo ✅ Test started!
echo Web interface: http://localhost:5000
echo.
echo To test dual-key system:
echo   python tools/client_key_generator.py
echo   python tools/provider_key_generator.py client_key.json
echo.
echo Press Ctrl+C in the application window to stop
echo ========================================