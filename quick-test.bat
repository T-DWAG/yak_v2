@echo off
echo ========================================
echo 🐂 Yak Analyzer Quick Docker Test
echo ========================================

echo [1/4] Building simplified Docker image...
docker build -f Dockerfile.simple -t yak-analyzer-simple . || goto :error

echo [2/4] Starting container...
docker run -d --name yak-test -p 5000:5000 -v %cd%\tools:/app/tools yak-analyzer-simple || goto :error

echo [3/4] Waiting for service to start...
timeout /t 10

echo [4/4] Testing health endpoint...
curl -f http://localhost:5000/health || echo Health check failed

echo.
echo ========================================
echo ✅ Test complete!
echo Web interface: http://localhost:5000
echo.
echo To test dual-key system:
echo   docker exec yak-test python tools/client_key_generator.py
echo   docker exec yak-test python tools/provider_key_generator.py client_key.json
echo.
echo To stop: docker stop yak-test && docker rm yak-test
echo ========================================
goto :end

:error
echo ❌ Build failed!
exit /b 1

:end