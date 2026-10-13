@echo off
rem Opens the web page for trying the agent. Press Ctrl+C to stop it.
call "%~dp0start.bat" -m schedagent web %*
