@echo off
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
cd /d "%~dp0"
if not exist "main.py" goto missing_project
if not exist ".venv\Scripts\python.exe" goto missing_setup
if not exist "check_install.py" goto missing_helper
".venv\Scripts\python.exe" check_install.py
if errorlevel 1 goto check_failed
echo.
echo Запускаю FunPayCardinal в этом окне...
echo.
".venv\Scripts\python.exe" main.py
set "FPC_START_EXIT=%ERRORLEVEL%"
echo.
echo Запуск завершён. Код выхода: %FPC_START_EXIT%
echo Если мастер сохранил настройки, запусти Start.bat ещё раз.
echo При ошибке её текст остаётся выше в этом окне.
pause
exit /b %FPC_START_EXIT%

:missing_project
echo Не найден main.py рядом с Start.bat.
echo Полностью распакуй архив через «Извлечь всё», затем запускай из папки проекта.
pause
exit /b 1

:missing_setup
echo Сначала запусти Setup.bat из этой же папки и дождись успешной установки.
pause
exit /b 1

:missing_helper
echo Не найден check_install.py. Скопируй все три файла исправления в папку с main.py.
pause
exit /b 1

:check_failed
echo.
echo Проверка зависимостей не прошла. Запусти Setup.bat и проверь результат установки.
pause
exit /b 1
