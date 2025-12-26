@echo off
REM Gateway Service Startup Script for Windows
REM Manages start, stop, restart, and status operations

setlocal enabledelayedexpansion

REM Configuration
set SCRIPT_DIR=%~dp0
REM Remove trailing backslash from SCRIPT_DIR for consistency
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set PROJECT_DIR=%SCRIPT_DIR%
set PID_FILE=%PROJECT_DIR%\.gateway.pid
set LOG_FILE=%PROJECT_DIR%\gateway.log
set PYTHON_CMD=python

REM Get command
if "%1"=="" goto :print_usage
if "%1"=="start" goto :start_service
if "%1"=="stop" goto :stop_service
if "%1"=="restart" goto :restart_service
if "%1"=="status" goto :status_service
if "%1"=="logs" goto :show_logs

:print_usage
echo Usage: %0 {start^|stop^|restart^|status^|logs}
echo.
echo Commands:
echo     start   - Start the gateway service
echo     stop    - Stop the gateway service
echo     restart - Restart the gateway service
echo     status  - Check service status
echo     logs    - Show service logs
echo.
echo Environment Variables:
echo     SERVER_PORT  - Server port (default: 8000)
echo     SERVER_HOST  - Server host (default: 0.0.0.0)
echo     ENVIRONMENT  - Environment (local, dev, qa, uat, prod)
echo.
exit /b 1

:start_service
echo Starting gateway service...
if not exist "%PROJECT_DIR%\venv" (
    echo Creating Python virtual environment...
    %PYTHON_CMD% -m venv "%PROJECT_DIR%\venv"
)

call "%PROJECT_DIR%\venv\Scripts\activate.bat"
echo Installing Python dependencies...
pip install -q -r "%PROJECT_DIR%\requirements.txt"

echo Starting service...
start /B "" %PYTHON_CMD% -m uvicorn app.main:app ^
    --host %SERVER_HOST% ^
    --port %SERVER_PORT% ^
    --log-level %LOG_LEVEL% > "%LOG_FILE%" 2>&1

timeout /t 2 /nobreak
echo Service started (check %LOG_FILE% for details)
goto :end

:stop_service
echo Stopping gateway service...
taskkill /F /FI "WINDOWTITLE eq*uvicorn*" 2>nul
if exist "%PID_FILE%" del "%PID_FILE%"
echo Service stopped
goto :end

:restart_service
echo Restarting gateway service...
call :stop_service
timeout /t 1 /nobreak
call :start_service
goto :end

:status_service
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Service is running
) else (
    echo Service is not running
)
goto :end

:show_logs
if not exist "%LOG_FILE%" (
    echo Log file not found: %LOG_FILE%
    exit /b 1
)
type "%LOG_FILE%"
goto :end

:end
endlocal
