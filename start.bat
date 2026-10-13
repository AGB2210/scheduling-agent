@echo off
rem Runs the project inside its own virtual environment (.venv).
rem The environment is created the first time this is run. Every time, the
rem packages named in pyproject.toml are checked, and installed if one is missing.
rem
rem   start.bat              run the tests
rem   start.bat -m pytest -q anything after start.bat goes to the venv's Python
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where python >nul 2>nul || (
        echo Python was not found. Install Python 3.12 or newer, then run this again.
        exit /b 1
    )
    echo Creating the virtual environment in .venv ...
    python -m venv .venv || exit /b 1
)

".venv\Scripts\python.exe" scripts\check_packages.py >nul 2>nul || (
    echo Installing the project and its packages ...
    ".venv\Scripts\python.exe" -m pip install --quiet -e ".[dev]" || exit /b 1
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m pytest
) else (
    ".venv\Scripts\python.exe" %*
)
