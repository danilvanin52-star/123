@echo off
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_setup
if not exist "check_api.py" goto missing_script
echo Проверка STEAM.RU только чтением. Покупок и списаний не будет.
echo Ключ и секрет вводятся скрыто. Не отправляй их в чат.
echo.
".venv\Scripts\python.exe" check_api.py
set "STEAMRU_CHECK_EXIT=%ERRORLEVEL%"
echo.
echo Проверка завершена. Код выхода: %STEAMRU_CHECK_EXIT%
pause
exit /b %STEAMRU_CHECK_EXIT%

:missing_setup
echo Сначала запусти Setup.bat из этой папки.
pause
exit /b 1

:missing_script
echo Не найден check_api.py. Помести файл проверки рядом с main.py.
pause
exit /b 1
