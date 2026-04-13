@echo off
cd /d "%~dp0"
python -m pip install -q flask
python app.py
pause
