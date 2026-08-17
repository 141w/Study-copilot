@echo off
title Study Copilot Launcher
setlocal enabledelayedexpansion

echo ====== Study Copilot - AI Learning Assistant ======
echo Starting services...
echo.

set BACKEND_PORT=8000
set FRONTEND_PORT=3000
set CONDA_PYTHON=C:\Users\L\miniconda3\envs\study-c\python.exe
set SCRIPT_DIR=%~dp0

echo [1/4] Checking dependencies...
if not exist "%CONDA_PYTHON%" (
    echo ERROR: Conda python not found at %CONDA_PYTHON%
    pause
    exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found.
    pause
    exit /b 1
)

if exist "%SCRIPT_DIR%frontend\node_modules" (
    echo [OK] Frontend dependencies installed.
) else (
    echo [..] Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%frontend"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
    cd /d "%SCRIPT_DIR%"
    echo [OK] Frontend dependencies installed.
)

echo [2/4] Checking port usage...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do taskkill /f /pid %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Port check done.

echo [3/4] Starting backend...
start "StudyCopilot-Backend" cmd /c "title StudyCopilot-Backend && cd /d %SCRIPT_DIR%backend && %CONDA_PYTHON% run.py"
echo [..] Waiting for backend...
set RETRIES=0
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    if !RETRIES! lss 15 goto wait_backend
    echo [!!] Backend timeout, continuing...
) else (
    echo [OK] Backend ready!
)

echo [4/4] Starting frontend...
start "StudyCopilot-Frontend" cmd /c "title StudyCopilot-Frontend && cd /d %SCRIPT_DIR%frontend && npm run dev"
echo [..] Waiting for frontend...
set RETRIES=0
:wait_frontend
timeout /t 2 /nobreak >nul
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    if !RETRIES! lss 15 goto wait_frontend
    echo [!!] Frontend timeout, opening browser anyway...
) else (
    echo [OK] Frontend ready!
)

echo.
echo ====== All services started! ======
echo  Frontend: http://localhost:3000
echo  Backend:  http://localhost:8000/docs
echo.
start "" http://localhost:3000

cd /d "%SCRIPT_DIR%"

echo Press any key to close this window...
pause >nul
exit /b 0
