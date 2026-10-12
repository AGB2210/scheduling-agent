@echo off
rem Runs the project inside its own virtual environment (.venv).
rem The environment is created and filled the first time this is run.
rem
rem   start.bat              run the tests
rem   start.bat -m pytest -q anything after start.bat goes to the venv's Python
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the virtual environment in .venv ...
    python -m venv .venv || exit /b 1
    echo Installing the project and its packages ...
    ".venv\Scripts\python.exe" -m pip install --quiet -e ".[dev]" || (
        rmdir /s /q .venv
        exit /b 1
    )
)

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m pytest
) else (
    ".venv\Scripts\python.exe" %*
)
