@echo off
cd /d "%~dp0"
python run.py serve %*
if errorlevel 1 pause
