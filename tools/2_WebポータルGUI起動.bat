@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" "%~dp0demo2_web_portal.py"
    goto :EOF
)

python "%~dp0demo2_web_portal.py"
if %ERRORLEVEL% NEQ 0 pause
