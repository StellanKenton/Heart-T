@echo off
py -3 "%~dp0run.py" %*
if errorlevel 1 pause
