@echo off
cd /d "%~dp0"
python -m msm serve
if errorlevel 1 pause
