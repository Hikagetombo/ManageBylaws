@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" "%~dp0demo1_desktop_gui.py"
    goto :EOF
)

python "%~dp0demo1_desktop_gui.py"
if %ERRORLEVEL% NEQ 0 pause
