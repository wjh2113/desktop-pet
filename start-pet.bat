@echo off
cd /d "%~dp0"
set "PYTHONW=%LocalAppData%\Python\pythoncore-3.14-64\pythonw.exe"
if exist "%PYTHONW%" (
  start "Desktop Pet" "%PYTHONW%" pet.py
) else (
  start "Desktop Pet" pythonw pet.py
)
