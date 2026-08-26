@echo off
setlocal enabledelayedexpansion

echo ========================================================================
echo   PULSE -- Point-Level Understanding ^& Strategic Leverage Engine
echo   Embedded Real-Time Tactical Cockpit Launcher
echo ========================================================================
echo.

:: Step 1: Check uv package manager
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'uv' package manager not found in PATH.
    echo Please install Astral uv: https://github.com/astral-sh/uv
    echo or run: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

echo [1/4] Synchronizing Python virtual environment dependencies via uv...
call uv sync --all-extras
if %errorlevel% neq 0 (

    echo [ERROR] uv sync failed. Please verify pyproject.toml and network connection.
    pause
    exit /b 1
)
echo [OK] Virtual environment synchronized.
echo.

:: Step 2: Ensure operational directories exist
echo [2/4] Verifying directory structure and storage roots...
if not exist "logs" mkdir logs
if not exist "artifacts" mkdir artifacts
echo [OK] Operational directories verified.
echo.

:: Step 3: Verify model and mathematical artifacts
echo [3/4] Verifying pipeline artifacts...
set MISSING_ARTIFACTS=0

if not exist "artifacts\models\point_win_classifier\stratum_table.json" (
    echo [WARNING] Missing point-win classifier stratum table artifact.
    set MISSING_ARTIFACTS=1
)
if not exist "artifacts\models\pressure_deviation\pressure_deviation.json" (
    echo [WARNING] Missing pressure deviation model artifact.
    set MISSING_ARTIFACTS=1
)
if not exist "artifacts\models\game_theory\payoff_matrices.json" (
    echo [WARNING] Missing game-theoretic payoff matrices artifact.
    set MISSING_ARTIFACTS=1
)

if !MISSING_ARTIFACTS! equ 1 (
    echo.
    echo [INFO] Attempting to reproduce pipeline artifacts via DVC...
    call uv run dvc repro
    if %errorlevel% neq 0 (
        echo [WARNING] DVC reproduction returned non-zero exit code.
        echo Attempting to proceed with available local models...
    )
) else (
    echo [OK] All required model and solver artifacts verified.
)
echo.

:: Step 4: Launch FastAPI Tactical Cockpit Server
echo [4/4] Starting PULSE FastAPI streaming service and embedded Tactical Cockpit...
echo.
echo ========================================================================
echo   Tactical Cockpit URL : http://127.0.0.1:8000/
echo   Swagger OpenAPI Docs : http://127.0.0.1:8000/docs
echo   Health Status Check  : http://127.0.0.1:8000/health
echo ========================================================================
echo Checking and freeing port 8000 if previously occupied...
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500 }"

echo.
echo Launching default web browser in background (waiting for engine readiness)...
start "" powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { $res = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 1; if ($res.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000/'; break } } catch { Start-Sleep -Milliseconds 500 } }"

echo Starting uvicorn application server (Press CTRL+C to terminate)...
call uv run python -m src.api.main

endlocal
