@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if exist "%USERPROFILE%\anaconda3\Scripts\streamlit.exe" (
    "%USERPROFILE%\anaconda3\Scripts\streamlit.exe" run "%~dp0demo3_streamlit_app.py"
    goto :EOF
)

streamlit run "%~dp0demo3_streamlit_app.py"
pause
