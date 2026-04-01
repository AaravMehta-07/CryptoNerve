@echo off
:: =========================================================
:: Crypto Sentinel — Start both API + React UI
:: =========================================================

echo.
echo  ==============================================
echo   CRYPTO SENTINEL — Starting Services
echo  ==============================================
echo.

:: Start FastAPI backend in its own window
echo [1/2] Starting FastAPI backend on http://localhost:8000...
start "Crypto Sentinel API" cmd /k "cd /d c:\Aarav\Code\CyrptoNerve\crypto-sentinel && python -m uvicorn api.main:app --reload --port 8000 --host 0.0.0.0"

:: Wait a moment for API to boot
timeout /t 3 /nobreak >nul

:: Start React dev server
echo [2/2] Starting React UI on http://localhost:5173...
start "Crypto Sentinel UI" cmd /k "cd /d c:\Aarav\Code\CyrptoNerve\crypto-sentinel-ui && npm run dev"

echo.
echo  API  → http://localhost:8000
echo  UI   → http://localhost:5173
echo  Docs → http://localhost:8000/docs
echo.
echo  Opening UI in browser...
timeout /t 5 /nobreak >nul
start http://localhost:5173
