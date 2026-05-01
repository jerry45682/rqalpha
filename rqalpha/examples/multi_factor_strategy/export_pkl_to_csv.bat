@echo off
setlocal

if "%~1"=="" (
    echo Drag a RQAlpha .pkl result file onto this bat file.
    pause
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    set "PYTHON=python"
)

"%PYTHON%" "%SCRIPT_DIR%export_pkl_to_csv.py" "%~1"

if errorlevel 1 (
    echo Export failed. Please check the input file.
    pause
    exit /b 1
)

pause
