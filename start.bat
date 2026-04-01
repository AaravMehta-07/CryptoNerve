@echo off
setlocal EnableDelayedExpansion
title Crypto Sentinel — Launcher
color 0A

echo.
echo  ██████╗██████╗ ██╗   ██╗██████╗ ████████╗ ██████╗
echo  ██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔═══██╗
echo  ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║   ██║   ██║
echo  ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║   ██║   ██║
echo  ╚██████╗██║  ██║   ██║   ██║        ██║   ╚██████╔╝
echo   ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝    ╚═════╝
echo.
echo  AI Market Intelligence Terminal  -  Full Stack Launcher
echo  ═══════════════════════════════════════════════════════
echo.

set ROOT=c:\Aarav\Code\CyrptoNerve
set BACKEND=%ROOT%\crypto-sentinel
set FRONTEND=%ROOT%\crypto-sentinel-ui
set DB_SCRIPT=%BACKEND%\scripts\init_db.py
set DB_FILE=%BACKEND%\data\crypto_sentinel.db

:: ── Step 1: Init DB if missing ──────────────────────────────────────────────
echo  [1/4] Checking database...
if not exist "%BACKEND%\data\" mkdir "%BACKEND%\data"

if not exist "%DB_FILE%" (
    echo        DB not found — running init_db.py to create + seed...
    cd /d "%BACKEND%"
    python scripts\init_db.py
    if errorlevel 1 (
        echo  [ERROR] init_db.py failed. Check Python installation.
        pause
        exit /b 1
    )
    echo        Database initialised successfully.
) else (
    echo        Database found: %DB_FILE%
)

:: ── Step 2: Start FastAPI backend ───────────────────────────────────────────
echo.
echo  [2/4] Starting FastAPI backend  (http://localhost:8000)
echo         Logs will appear in the "API Server" window.
start "Crypto Sentinel — API Server" cmd /k ^
    "title Crypto Sentinel API ^& color 0B ^& cd /d %BACKEND% ^& echo. ^& echo  Starting Uvicorn... ^& echo. ^& python -m uvicorn api.main:app --reload --port 8000 --host 0.0.0.0 || (echo. ^& echo [ERROR] Uvicorn failed - check Python/deps ^& pause)"

:: ── Wait for API to be ready (poll /api/health) ─────────────────────────────
echo  [3/4] Waiting for API to respond...
set /a TRIES=0
:WAIT_LOOP
timeout /t 2 /nobreak >nul
curl -s -o nul -w "%%{http_code}" http://localhost:8000/api/health 2>nul | findstr "200" >nul
if not errorlevel 1 (
    echo        API is online!
    goto API_READY
)
set /a TRIES+=1
if %TRIES% lss 15 (
    echo        Still waiting... ^(%TRIES%/15^)
    goto WAIT_LOOP
)
echo        API did not respond in time — starting UI anyway.

:API_READY

:: ── Step 3: Start React dev server ──────────────────────────────────────────
echo.
echo  [4/4] Starting React UI  (http://localhost:5173)
start "Crypto Sentinel — UI Server" cmd /k ^
    "title Crypto Sentinel UI ^& color 0D ^& cd /d %FRONTEND% ^& echo. ^& echo  Starting Vite dev server... ^& echo. ^& npm run dev || (echo. ^& echo [ERROR] npm run dev failed - run 'npm install' first ^& pause)"

:: ── Wait then open browser ──────────────────────────────────────────────────
timeout /t 4 /nobreak >nul
echo.
echo  ═══════════════════════════════════════════════════════
echo    UI   →  http://localhost:5173
echo    API  →  http://localhost:8000
echo    Docs →  http://localhost:8000/docs
echo  ═══════════════════════════════════════════════════════
echo.
echo  Opening browser...
start http://localhost:5173

echo.
echo  Both servers are running in separate windows.
echo  Close those windows to stop the servers.
echo.
pause
