@echo off
REM Docker startup script for Windows
REM Yak Similarity Analyzer Docker Setup

echo ======================================================
echo 🐂 Yak Similarity Analyzer Docker Setup
echo ======================================================

REM Create necessary directories
if not exist data mkdir data
if not exist uploads mkdir uploads
if not exist results mkdir results
if not exist license_data mkdir license_data
if not exist dual_keys mkdir dual_keys

echo ------------------------------------------------------
echo 📋 Quick Start Instructions:
echo.
echo 1. Build and run with Docker Compose:
echo    docker-compose up --build
echo.
echo 2. Or run with Docker directly:
echo    docker build -t yak-analyzer .
echo    docker run -p 5000:5000 -v %cd%/data:/app/data yak-analyzer
echo.
echo 3. Access the web interface:
echo    http://localhost:5000
echo.
echo 4. For first-time setup:
echo    docker exec -it ^<container-name^> python tools/client_key_generator.py
echo.
echo 5. To generate authorization:
echo    docker exec -it ^<container-name^> python tools/provider_key_generator.py client_key.json
echo ------------------------------------------------------

if "%1"=="run" (
    echo Starting Yak Similarity Analyzer...
    python run.py
) else (
    echo Use 'docker-start.bat run' to start the application
)